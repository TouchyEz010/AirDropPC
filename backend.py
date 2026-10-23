"""
backend.py — AirDrop PC core
  • Config (persistent PIN / port / save folder)
  • Network helpers (LAN IP, free port)
  • Bonjour / mDNS advertiser  ->  http://airdrop-pc.local:<port>
  • FastAPI streaming upload server (raw body + streaming multipart, >4 GB safe)
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import mimetypes
import os
import re
import secrets
import shutil
import socket
import threading
import time
import unicodedata
import uuid
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Optional, Protocol
from urllib.parse import quote, unquote

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect
from zeroconf import IPVersion, ServiceInfo, Zeroconf

try:  # python-multipart >= 0.0.13
    from python_multipart.multipart import MultipartParser, parse_options_header
except ImportError:  # older python-multipart
    from multipart.multipart import MultipartParser, parse_options_header

from web_ui import render_index

log = logging.getLogger("airdrop")

APP_NAME = "AirDrop PC"
APP_VERSION = "1.0.0"
MDNS_HOSTNAME = "airdrop-pc"
DEFAULT_PORT = 8080

FLUSH_BYTES = 4 * 1024 * 1024        # write to disk in 4 MB blocks, off the event loop
PROGRESS_INTERVAL = 0.10             # seconds between GUI progress events
DISK_RESERVE = 256 * 1024 * 1024     # always leave 256 MB free on the drive
PART_SUFFIX = ".airdrop-part"
CGNAT = ipaddress.ip_network("100.64.0.0/10")
EXTRA_EXT = {"image/heic": ".heic", "image/heif": ".heif", "image/jpeg": ".jpg",
             "video/quicktime": ".mov", "video/mp4": ".mp4"}


# ─────────────────────────── Paths & config ───────────────────────────
def app_data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    path = Path(base) / "AirDropPC"
    path.mkdir(parents=True, exist_ok=True)
    return path


def windows_downloads_dir() -> Path:
    """Real Downloads folder (respects relocated / OneDrive folders)."""
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                            ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

            folder_id = GUID(0x374DE290, 0x123F, 0x4565,
                             (ctypes.c_ubyte * 8)(0x91, 0x64, 0x39, 0xC4, 0x92, 0x5E, 0x46, 0x7B))
            out = ctypes.c_wchar_p()
            hr = ctypes.windll.shell32.SHGetKnownFolderPath(
                ctypes.byref(folder_id), 0, None, ctypes.byref(out))
            if hr == 0 and out.value:
                path = Path(out.value)
                ctypes.windll.ole32.CoTaskMemFree(out)
                return path
        except Exception:
            log.exception("SHGetKnownFolderPath failed")
    return Path.home() / "Downloads"


@dataclass
class Config:
    pin: str = ""
    port: int = DEFAULT_PORT
    save_dir: str = ""
    device_name: str = ""

    @staticmethod
    def file() -> Path:
        return app_data_dir() / "config.json"

    @classmethod
    def load(cls) -> "Config":
        data: dict[str, Any] = {}
        try:
            data = json.loads(cls.file().read_text("utf-8"))
        except FileNotFoundError:
            pass
        except Exception:
            log.warning("config.json is corrupt - regenerating")
        known = {f.name for f in fields(cls)}
        cfg = cls(**{k: v for k, v in data.items() if k in known})
        cfg.pin = str(cfg.pin)
        if not (cfg.pin.isdigit() and len(cfg.pin) == 6):
            cfg.pin = f"{secrets.randbelow(1_000_000):06d}"
        try:
            cfg.port = int(cfg.port)
        except (TypeError, ValueError):
            cfg.port = DEFAULT_PORT
        if not cfg.save_dir:
            cfg.save_dir = str(windows_downloads_dir() / "AirDrop")
        if not cfg.device_name:
            cfg.device_name = socket.gethostname() or "Windows PC"
        cfg.save()
        return cfg

    def save(self) -> None:
        self.file().write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), "utf-8")


# ─────────────────────────── Network ───────────────────────────
def get_local_ip() -> str:
    """IPv4 of the interface that owns the default route (usually Wi-Fi/Ethernet)."""
    for probe in ("8.8.8.8", "10.255.255.255"):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect((probe, 80))          # UDP connect sends no packets
            ip = s.getsockname()[0]
            if ip and not ip.startswith(("127.", "0.")):
                return ip
        except OSError:
            pass
        finally:
            s.close()
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith(("127.", "169.254.")):
                return ip
    except OSError:
        pass
    return "127.0.0.1"


def find_free_port(preferred: int, attempts: int = 20) -> int:
    for port in range(preferred, preferred + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free TCP port between {preferred} and {preferred + attempts - 1}")


def _is_lan(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or (ip.version == 4 and ip in CGNAT)


# ─────────────────────────── mDNS / Bonjour ───────────────────────────
class MDNSAdvertiser:
    """Publishes _http._tcp and answers A-queries for airdrop-pc.local."""
    SERVICE_TYPE = "_http._tcp.local."

    def __init__(self, port: int, device_name: str):
        self.port = port
        self.device_name = device_name
        self._zc: Optional[Zeroconf] = None
        self._info: Optional[ServiceInfo] = None
        self._lock = threading.Lock()

    def start(self, ip: str) -> tuple[bool, str]:
        """Blocking (probing takes ~1–2 s) – call from a worker thread."""
        with self._lock:
            self._stop_locked()
            try:
                instance = f"{APP_NAME} - {self.device_name}".encode()[:60].decode(errors="ignore")
                self._info = ServiceInfo(
                    self.SERVICE_TYPE,
                    f"{instance}.{self.SERVICE_TYPE}",
                    addresses=[socket.inet_aton(ip)],
                    port=self.port,
                    properties={"path": "/", "app": APP_NAME, "version": APP_VERSION},
                    server=f"{MDNS_HOSTNAME}.local.",
                )
                self._zc = Zeroconf(interfaces=[ip], ip_version=IPVersion.V4Only)
                self._zc.register_service(self._info, allow_name_change=True)
                log.info("mDNS registered %s.local -> %s:%s", MDNS_HOSTNAME, ip, self.port)
                return True, f"{MDNS_HOSTNAME}.local"
            except Exception as exc:
                log.exception("mDNS registration failed")
                self._stop_locked()
                return False, str(exc)

    def _stop_locked(self) -> None:
        if self._zc:
            try:
                if self._info:
                    self._zc.unregister_service(self._info)
            except Exception:
                pass
            try:
                self._zc.close()
            except Exception:
                pass
        self._zc = None
        self._info = None

    def stop(self) -> None:
        with self._lock:
            self._stop_locked()


# ─────────────────────────── File handling ───────────────────────────
_WIN_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WIN_RESERVED = {"CON", "PRN", "AUX", "NUL",
                 *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def sanitize_filename(raw: Optional[str], fallback_ext: str = "") -> str:
    name = unicodedata.normalize("NFC", raw or "")
    name = name.replace("\\", "/").split("/")[-1]          # no path traversal
    name = _WIN_INVALID.sub("_", name).strip().rstrip(". ")
    if not name:
        name = f"AirDrop_{time.strftime('%Y%m%d_%H%M%S')}"
    stem, ext = os.path.splitext(name)
    if len(ext) > 16:                                      # not a real extension
        stem, ext = stem + ext, ""
    if not ext and fallback_ext:
        ext = fallback_ext
    if stem.split(".")[0].upper() in _WIN_RESERVED:
        stem = f"_{stem}"
    stem = stem[: max(1, 150 - len(ext))]
    return f"{stem}{ext}"


def decode_header_filename(value: Optional[str]) -> str:
    """Header values arrive latin-1 decoded; repair raw UTF-8 then URL-decode."""
    if not value:
        return ""
    try:
        value = value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return unquote(value)


def _decode_bytes_name(raw: bytes) -> str:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    if "''" in text:                                       # RFC 5987: UTF-8''%E0%B8...
        charset, _, encoded = text.partition("''")
        text = unquote(encoded, encoding=charset or "utf-8", errors="replace")
    return text


def _ext_for(content_type: str) -> str:
    ctype = (content_type or "").split(";")[0].strip().lower()
    if not ctype or ctype == "application/octet-stream":
        return ""
    return EXTRA_EXT.get(ctype) or mimetypes.guess_extension(ctype) or ""


class FileStore:
    def __init__(self, directory: Path):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._reserved: set[str] = set()
        for stale in self.dir.glob(f"*{PART_SUFFIX}"):     # leftovers from a crash
            try:
                stale.unlink()
            except OSError:
                pass

    def reserve(self, filename: str) -> Path:
        stem, ext = os.path.splitext(filename)
        with self._lock:
            self.dir.mkdir(parents=True, exist_ok=True)
            n = 0
            while True:
                name = filename if n == 0 else f"{stem} ({n}){ext}"
                path = self.dir / name
                if name.lower() not in self._reserved and not path.exists():
                    self._reserved.add(name.lower())
                    return path
                n += 1

    def release(self, path: Path) -> None:
        with self._lock:
            self._reserved.discard(path.name.lower())

    def ensure_space(self, needed: int) -> None:
        if needed <= 0:
            return
        self.dir.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(self.dir).free
        if free < needed + DISK_RESERVE:
            raise HTTPException(507, f"Not enough disk space on the PC ({free // 2**20} MB free)")


class TransferEvents(Protocol):
    def on_start(self, tid: str, name: str, total: int) -> None: ...
    def on_progress(self, tid: str, received: int) -> None: ...
    def on_done(self, tid: str, path: str, size: int) -> None: ...
    def on_error(self, tid: str, message: str) -> None: ...
    def on_outbox_download(self, oid: str, count: int) -> None: ...


class IncomingFile:
    """Streams one file to <name>.airdrop-part and renames it on success."""

    def __init__(self, store: FileStore, events: TransferEvents, filename: str, expected: int):
        self.store, self.events = store, events
        self.id = uuid.uuid4().hex
        self.final_path = store.reserve(filename)
        self.part_path = self.final_path.with_name(self.final_path.name + PART_SUFFIX)
        self.received = 0
        self._buf = bytearray()
        self._last_emit = 0.0
        self._closed = False
        try:
            self._fh = open(self.part_path, "wb")
        except OSError:
            store.release(self.final_path)
            raise
        events.on_start(self.id, self.final_path.name, expected or 0)

    async def write(self, data: bytes) -> None:
        self._buf += data
        self.received += len(data)
        if len(self._buf) >= FLUSH_BYTES:
            await self._flush()
        now = time.monotonic()
        if now - self._last_emit >= PROGRESS_INTERVAL:
            self._last_emit = now
            self.events.on_progress(self.id, self.received)

    async def _flush(self) -> None:
        if self._buf:
            chunk, self._buf = self._buf, bytearray()
            await run_in_threadpool(self._fh.write, chunk)

    def _close(self) -> None:
        if not self._closed:
            self._closed = True
            self._fh.close()

    def _finalize_sync(self) -> Path:
        self._close()
        target, n = self.final_path, 1
        while True:
            try:
                os.rename(self.part_path, target)   # never overwrites an existing file
                break
            except FileExistsError:
                target = self.final_path.with_name(f"{self.final_path.stem} ~{n}{self.final_path.suffix}")
                n += 1
        self.store.release(self.final_path)
        return target

    async def commit(self) -> Path:
        await self._flush()
        final = await run_in_threadpool(self._finalize_sync)
        self.events.on_done(self.id, str(final), self.received)
        return final

    def abort(self, reason: str) -> None:
        try:
            self._close()
        except Exception:
            pass
        try:
            self.part_path.unlink(missing_ok=True)
        except OSError:
            log.warning("Could not delete %s", self.part_path)
        self.store.release(self.final_path)
        self.events.on_error(self.id, reason)


def _reason(exc: BaseException) -> str:
    if isinstance(exc, (ClientDisconnect, asyncio.CancelledError)):
        return "Connection lost"
    if isinstance(exc, HTTPException):
        return str(exc.detail)
    return str(exc) or exc.__class__.__name__


async def _receive_raw(request: Request, filename: str, length: int,
                       store: FileStore, events: TransferEvents) -> list[Path]:
    incoming = IncomingFile(store, events, filename, length)
    try:
        async for chunk in request.stream():
            if chunk:
                await incoming.write(chunk)
        if length and incoming.received != length:
            raise ClientDisconnect()
        return [await incoming.commit()]
    except BaseException as exc:
        incoming.abort(_reason(exc))
        raise


async def _receive_multipart(request: Request, content_type: str, length: int,
                             store: FileStore, events: TransferEvents) -> list[Path]:
    """Streaming multipart parser – used by iOS Shortcuts (Request Body: Form)."""
    _, params = parse_options_header(content_type)
    boundary = params.get(b"boundary")
    if not boundary:
        raise HTTPException(400, "Missing multipart boundary")

    pending: list[tuple[str, Any]] = []
    hdr_field, hdr_value = bytearray(), bytearray()
    part_headers: dict[bytes, bytes] = {}

    def on_part_begin() -> None:
        part_headers.clear()

    def on_header_field(data: bytes, start: int, end: int) -> None:
        hdr_field.extend(data[start:end])

    def on_header_value(data: bytes, start: int, end: int) -> None:
        hdr_value.extend(data[start:end])

    def on_header_end() -> None:
        part_headers[bytes(hdr_field).strip().lower()] = bytes(hdr_value).strip()
        hdr_field.clear()
        hdr_value.clear()

    def on_headers_finished() -> None:
        pending.append(("headers", dict(part_headers)))

    def on_part_data(data: bytes, start: int, end: int) -> None:
        pending.append(("data", bytes(data[start:end])))

    def on_part_end() -> None:
        pending.append(("end", None))

    parser = MultipartParser(boundary, {
        "on_part_begin": on_part_begin, "on_header_field": on_header_field,
        "on_header_value": on_header_value, "on_header_end": on_header_end,
        "on_headers_finished": on_headers_finished, "on_part_data": on_part_data,
        "on_part_end": on_part_end,
    })

    saved: list[Path] = []
    current: Optional[IncomingFile] = None
    try:
        async for chunk in request.stream():
            if not chunk:
                continue
            parser.write(chunk)
            for kind, payload in pending:
                if kind == "headers":
                    _, opts = parse_options_header(payload.get(b"content-disposition", b""))
                    raw = opts.get(b"filename*") or opts.get(b"filename")
                    if raw is not None:
                        ctype = payload.get(b"content-type", b"").decode("latin-1")
                        name = sanitize_filename(_decode_bytes_name(raw), _ext_for(ctype))
                        current = IncomingFile(store, events, name, length)
                elif kind == "data" and current is not None:
                    await current.write(payload)
                elif kind == "end" and current is not None:
                    saved.append(await current.commit())
                    current = None
            pending.clear()
        parser.finalize()
    except BaseException as exc:
        if current is not None:
            current.abort(_reason(exc))
        raise
    if current is not None:
        current.abort("Upload incomplete")
        raise HTTPException(400, "Upload incomplete")
    if not saved:
        raise HTTPException(400, "No file field found in the form data")
    return saved


# ─────────────────────────── Auth ───────────────────────────
class AuthGuard:
    MAX_FAILS = 8
    LOCKOUT = 60.0

    def __init__(self, pin: str):
        self._pin = pin.encode()
        self._fails: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def verify(self, request: Request) -> None:
        host = request.client.host if request.client else ""
        if not _is_lan(host):
            raise HTTPException(403, "Only devices on the local network may connect")
        now = time.monotonic()
        with self._lock:
            count, until = self._fails.get(host, (0, 0.0))
            if until > now:
                raise HTTPException(429, "Too many wrong PIN attempts. Try again in a minute.")
        supplied = (request.headers.get("x-pin") or request.query_params.get("pin") or "").strip().encode()
        if secrets.compare_digest(supplied, self._pin):
            with self._lock:
                self._fails.pop(host, None)
            return
        with self._lock:
            count += 1
            self._fails[host] = (0, now + self.LOCKOUT) if count >= self.MAX_FAILS else (count, 0.0)
        raise HTTPException(401, "Invalid PIN")

# ─────────────────────────── PC -> iPhone (Outbox) ───────────────────────────
for _mime, _ext in (("image/heic", ".heic"), ("image/heif", ".heif"), ("image/webp", ".webp"),
                    ("video/quicktime", ".mov"), ("video/mp4", ".mp4"), ("audio/mp4", ".m4a")):
    mimetypes.add_type(_mime, _ext)

STREAM_CHUNK = 1024 * 1024
_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


@dataclass
class OutgoingFile:
    id: str
    path: Path
    name: str
    size: int
    mime: str
    added: float
    downloads: int = 0

    def public(self) -> dict:
        return {"id": self.id, "name": self.name, "size": self.size,
                "mime": self.mime, "added": self.added, "downloads": self.downloads}


class Outbox:
    """Files the PC user offers to the iPhone. Served in place – never copied."""

    def __init__(self) -> None:
        self._items: dict[str, OutgoingFile] = {}
        self._lock = threading.Lock()
        self.version = 0

    def add(self, path: Path) -> OutgoingFile:
        path = Path(path).resolve()
        if not path.is_file():
            raise FileNotFoundError(str(path))
        with self._lock:
            for item in self._items.values():
                if item.path == path:
                    return item
            item = OutgoingFile(
                id=uuid.uuid4().hex[:12], path=path,
                name=unicodedata.normalize("NFC", path.name), size=path.stat().st_size,
                mime=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                added=time.time())
            self._items[item.id] = item
            self.version += 1
            return item

    def remove(self, oid: str) -> None:
        with self._lock:
            if self._items.pop(oid, None):
                self.version += 1

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self.version += 1

    def get(self, oid: str) -> Optional[OutgoingFile]:
        with self._lock:
            return self._items.get(oid)

    def latest(self) -> Optional[OutgoingFile]:
        with self._lock:
            return max(self._items.values(), key=lambda i: i.added, default=None)

    def snapshot(self) -> tuple[int, list[dict]]:
        with self._lock:
            items = sorted(self._items.values(), key=lambda i: i.added, reverse=True)
            return self.version, [i.public() for i in items]

    def mark_downloaded(self, oid: str) -> int:
        with self._lock:
            item = self._items.get(oid)
            if not item:
                return 0
            item.downloads += 1
            return item.downloads


def content_disposition(kind: str, name: str) -> str:
    stem, ext = os.path.splitext(name)
    ascii_stem = stem.encode("ascii", "ignore").decode().replace('"', "").replace("\\", "").strip() or "file"
    ascii_ext = ext.encode("ascii", "ignore").decode()
    return f"{kind}; filename=\"{ascii_stem}{ascii_ext}\"; filename*=UTF-8''{quote(name, safe='')}"


def ranged_file_response(request: Request, path: Path, name: str, mime: str,
                         attachment: bool) -> tuple[Response, bool]:
    """Streams a file with HTTP Range support (required for video in iOS Safari).
    Returns (response, counts_as_download)."""
    size = path.stat().st_size
    headers = {"Accept-Ranges": "bytes", "Cache-Control": "no-store",
               "Content-Disposition": content_disposition("attachment" if attachment else "inline", name)}
    start, end, status = 0, size - 1, 200
    m = _RANGE_RE.match((request.headers.get("range") or "").strip())
    if m and size and (m.group(1) or m.group(2)):
        if m.group(1):
            start = int(m.group(1))
            end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
        else:                                   # suffix range: bytes=-500
            start, end = max(0, size - int(m.group(2))), size - 1
        if start >= size or start > end:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"}), False
        status = 206
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    length = max(0, end - start + 1)
    headers["Content-Length"] = str(length)

    def body():
        with open(path, "rb") as fh:
            fh.seek(start)
            left = length
            while left > 0:
                chunk = fh.read(min(STREAM_CHUNK, left))
                if not chunk:
                    break
                left -= len(chunk)
                yield chunk

    resp = StreamingResponse(body(), status_code=status, media_type=mime, headers=headers)
    return resp, attachment and start == 0


# ─────────────────────────── FastAPI app ───────────────────────────
def create_app(cfg: Config, events: TransferEvents, store: FileStore, outbox: Outbox) -> FastAPI:
    app = FastAPI(title=APP_NAME, docs_url=None, redoc_url=None, openapi_url=None)
    guard = AuthGuard(cfg.pin)
    page = render_index(cfg.device_name)
    no_cache = {"Cache-Control": "no-store"}

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        return HTMLResponse(page, headers=no_cache)

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        return Response(status_code=204)

    @app.get("/api/info")
    async def info() -> JSONResponse:
        return JSONResponse({"app": APP_NAME, "version": APP_VERSION, "name": cfg.device_name},
                            headers=no_cache)

    @app.post("/api/verify")
    async def verify(request: Request) -> dict:
        guard.verify(request)
        return {"ok": True}

    # ---------- iPhone -> PC ----------
    @app.post("/api/upload")
    async def upload(request: Request):
        guard.verify(request)
        try:
            length = max(0, int(request.headers.get("content-length") or 0))
        except ValueError:
            length = 0
        store.ensure_space(length)
        ctype = request.headers.get("content-type", "")
        try:
            if ctype.lower().startswith("multipart/form-data"):
                saved = await _receive_multipart(request, ctype, length, store, events)
            else:
                name = sanitize_filename(decode_header_filename(request.headers.get("x-filename")),
                                         _ext_for(ctype))
                saved = await _receive_raw(request, name, length, store, events)
        except ClientDisconnect:
            log.warning("Client disconnected during upload")
            return Response(status_code=400)
        except OSError as exc:
            log.exception("Disk error while saving upload")
            raise HTTPException(500, f"Could not save file on PC: {exc.strerror or exc}")
        log.info("Saved: %s", ", ".join(p.name for p in saved))
        return {"ok": True, "saved": [p.name for p in saved]}

    # ---------- PC -> iPhone ----------
    def serve_outgoing(request: Request, item: OutgoingFile, attachment: bool) -> Response:
        if not item.path.is_file():
            raise HTTPException(410, "This file was moved or deleted on the PC")
        resp, counts = ranged_file_response(request, item.path, item.name, item.mime, attachment)
        if counts:
            events.on_outbox_download(item.id, outbox.mark_downloaded(item.id))
        return resp

    @app.get("/api/outbox")
    async def outbox_list(request: Request) -> JSONResponse:
        guard.verify(request)
        version, items = outbox.snapshot()
        return JSONResponse({"version": version, "items": items}, headers=no_cache)

    @app.get("/api/outbox/latest")          # must be declared before /api/outbox/{oid}
    async def outbox_latest(request: Request):
        guard.verify(request)
        item = outbox.latest()
        if not item:
            raise HTTPException(404, "Nothing to send - add files on the PC first")
        return serve_outgoing(request, item, attachment=True)

    @app.get("/api/outbox/{oid}")
    async def outbox_file(oid: str, request: Request):
        guard.verify(request)
        item = outbox.get(oid)
        if not item:
            raise HTTPException(404, "This file is no longer shared")
        return serve_outgoing(request, item, attachment=request.query_params.get("dl") == "1")

    return app


# ─────────────────────────── Server thread ───────────────────────────
class _ThreadedServer(uvicorn.Server):
    def install_signal_handlers(self) -> None:   # uvicorn < 0.29: no signals off main thread
        pass


class ServerThread(threading.Thread):
    def __init__(self, app: FastAPI, port: int):
        super().__init__(name="airdrop-http", daemon=True)
        self.port = port
        config = uvicorn.Config(app, host="0.0.0.0", port=port, log_config=None,
                                access_log=False, timeout_keep_alive=20, server_header=False)
        self.server = _ThreadedServer(config)

    def run(self) -> None:
        try:
            self.server.run()
        except BaseException:          # includes SystemExit raised on bind failure
            log.exception("HTTP server stopped")

    def wait_ready(self, timeout: float = 8.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.server.started:
                return True
            if not self.is_alive():
                return False
            time.sleep(0.05)
        return bool(self.server.started)

    def stop(self) -> None:
        self.server.should_exit = True