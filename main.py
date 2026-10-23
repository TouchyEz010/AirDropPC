"""
main.py — AirDrop PC (Windows desktop app, PyQt6)

  • iPhone -> PC : radar, live transfer list, Windows toast
  • PC -> iPhone : drag files onto the window (or "Add Files…"); the iPhone
                   downloads them from the same Safari page or an iOS Shortcut

Run:  python main.py        (pythonw main.py = no console window)
"""
from __future__ import annotations

import ctypes
import itertools
import logging
import math
import os
import subprocess
import sys
import tempfile
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

import qrcode
from PyQt6.QtCore import QEvent, QLockFile, QObject, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (QAction, QColor, QFont, QFontDatabase, QGuiApplication, QIcon, QImage,
                         QImageReader, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                         QRadialGradient)
from PyQt6.QtWidgets import (QApplication, QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QLabel,
                             QMenu, QMessageBox, QProgressBar, QPushButton, QScrollArea,
                             QSizePolicy, QStackedWidget, QSystemTrayIcon, QVBoxLayout, QWidget)

import backend

log = logging.getLogger("airdrop.gui")

# ── Apple dark palette ──
BG, SURFACE, SURFACE_2, BORDER = "#0D0D0E", "#1C1C1E", "#2C2C2E", "#3A3A3C"
BLUE, CYAN = "#0A84FF", "#64D2FF"
TEXT, TEXT_2 = "#F5F5F7", "#8E8E93"
GREEN, ORANGE, RED = "#30D158", "#FF9F0A", "#FF453A"
FONT_FAMILY = "Segoe UI"

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".heif", ".tif", ".tiff"}
VIDEO_EXT = {".mov", ".mp4", ".m4v", ".avi", ".mkv", ".webm", ".hevc"}
AUDIO_EXT = {".mp3", ".m4a", ".wav", ".aac", ".flac", ".caf"}
DOC_EXT = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".rtf",
           ".pages", ".numbers", ".key", ".csv"}
ARCHIVE_EXT = {".zip", ".rar", ".7z", ".tar", ".gz"}
TOAST_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
_preview_seq = itertools.count()

QSS = """
* { font-family: "%FONT%"; color: #F5F5F7; }
QFrame#Root { background: #0D0D0E; border: 1px solid #2C2C2E; border-radius: 18px; }
QFrame#Root[drop="true"] { border: 2px solid #64D2FF; }
QLabel#WindowTitle { color: #8E8E93; font-size: 13px; font-weight: 600; }
QLabel#H1 { font-size: 24px; font-weight: 700; }
QLabel#Sub { color: #8E8E93; font-size: 13px; }
QLabel#Section { font-size: 15px; font-weight: 600; }
QLabel#Caption { color: #8E8E93; font-size: 12px; }
QLabel#Caption[tone="ok"] { color: #30D158; }
QLabel#Caption[tone="err"] { color: #FF453A; }
QLabel#Overline { color: #8E8E93; font-size: 11px; font-weight: 600; }
QLabel#Mono { font-family: "Cascadia Mono", "Consolas"; font-size: 13px; }
QLabel#Pin { font-size: 24px; font-weight: 700; color: #64D2FF; }
QLabel#ItemTitle { font-size: 14px; font-weight: 600; }
QLabel#PillText { font-size: 12px; font-weight: 600; }
QFrame#Card { background: #1C1C1E; border: 1px solid #2C2C2E; border-radius: 16px; }
QFrame#TransferItem { background: #1C1C1E; border: 1px solid #2C2C2E; border-radius: 14px; }
QFrame#TransferItem:hover { border: 1px solid #3A3A3C; }
QFrame#Pill { background: #1C1C1E; border: 1px solid #2C2C2E; border-radius: 12px; }
QFrame#Sep { background: #2C2C2E; border: none; min-height: 1px; max-height: 1px; }
QFrame#Segmented { background: #1C1C1E; border: 1px solid #2C2C2E; border-radius: 9px; }
QPushButton { border: none; }
QPushButton#Segment { background: transparent; color: #8E8E93; border-radius: 7px; padding: 5px 14px;
                      font-size: 12px; font-weight: 600; }
QPushButton#Segment:checked { background: #3A3A3C; color: #F5F5F7; }
QPushButton#Segment:hover:!checked { color: #F5F5F7; }
QPushButton#Primary { background: #0A84FF; color: white; border-radius: 10px; padding: 9px 14px;
                      font-size: 13px; font-weight: 600; }
QPushButton#Primary:hover { background: #3395FF; }
QPushButton#Primary:pressed { background: #0060DF; }
QPushButton#Ghost { background: #2C2C2E; border: 1px solid #3A3A3C; border-radius: 8px;
                    padding: 5px 10px; font-size: 12px; }
QPushButton#Ghost:hover { background: #3A3A3C; }
QPushButton#Link { background: transparent; color: #0A84FF; font-size: 13px; font-weight: 600; padding: 4px 6px; }
QPushButton#Link:hover { color: #64D2FF; }
QProgressBar { background: #2C2C2E; border: none; border-radius: 2px; }
QProgressBar::chunk { border-radius: 2px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0A84FF, stop:1 #64D2FF); }
QProgressBar[state="done"]::chunk { background: #30D158; }
QProgressBar[state="error"]::chunk { background: #FF453A; }
QStackedWidget { background: transparent; }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
QScrollBar::handle:vertical { background: #3A3A3C; border-radius: 3px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QMenu { background: #1C1C1E; border: 1px solid #3A3A3C; padding: 4px; }
QMenu::item { padding: 6px 18px; border-radius: 6px; }
QMenu::item:selected { background: #0A84FF; }
QMenu::separator { height: 1px; background: #3A3A3C; margin: 4px 8px; }
QToolTip { background: #2C2C2E; color: #F5F5F7; border: 1px solid #3A3A3C; padding: 4px 8px; }
QMessageBox { background: #1C1C1E; }
QMessageBox QPushButton { background: #2C2C2E; border: 1px solid #3A3A3C; border-radius: 6px; padding: 5px 14px; }
QFileDialog { background: #1C1C1E; }
"""


# ───────────────────────── helpers ─────────────────────────
def human(n: float) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            if unit == "B":
                return f"{n:.0f} B"
            return f"{n:.1f} {unit}" if n < 100 else f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def fmt_eta(sec: float) -> str:
    if sec < 60:
        return f"{int(sec) + 1} s left"
    if sec < 3600:
        return f"{int(sec // 60) + 1} min left"
    return f"{int(sec // 3600)} h {int(sec % 3600 // 60)} min left"


def repolish(w: QWidget, **props) -> None:
    for k, v in props.items():
        w.setProperty(k, v)
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


def pick_font_family() -> str:
    families = set(QFontDatabase.families())
    for name in ("SF Pro Display", "SF Pro Text", "Segoe UI Variable Display",
                 "Segoe UI Variable Text", "Segoe UI"):
        if name in families:
            return name
    return QApplication.font().family()


def reveal_in_explorer(path: str) -> None:
    if path and os.path.exists(path):
        subprocess.Popen(f'explorer /select,"{os.path.normpath(path)}"')


def open_with_default_app(path: str) -> None:
    if path and os.path.exists(path):
        os.startfile(path)


def draw_receive_glyph(p: QPainter, c: QPointF, s: float, color: QColor) -> None:
    pen = QPen(color, max(1.5, s * 0.17))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    x, y = c.x(), c.y()
    p.drawLine(QPointF(x, y - s * 0.95), QPointF(x, y + s * 0.25))
    head = QPainterPath()
    head.moveTo(x - s * 0.5, y - s * 0.25)
    head.lineTo(x, y + s * 0.25)
    head.lineTo(x + s * 0.5, y - s * 0.25)
    p.drawPath(head)
    tray = QPainterPath()
    tray.moveTo(x - s, y + s * 0.15)
    tray.lineTo(x - s, y + s * 0.85)
    tray.lineTo(x + s, y + s * 0.85)
    tray.lineTo(x + s, y + s * 0.15)
    p.drawPath(tray)


def make_app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g = QLinearGradient(0, 0, size, size)
        g.setColorAt(0, QColor(BLUE))
        g.setColorAt(1, QColor(CYAN))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawRoundedRect(QRectF(0, 0, size, size), size * 0.23, size * 0.23)
        draw_receive_glyph(p, QPointF(size / 2, size / 2), size * 0.28, QColor("white"))
        p.end()
        icon.addPixmap(pm)
    return icon


def make_qr_pixmap(data: str, size: int, dpr: float) -> QPixmap:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, border=0)
    qr.add_data(data)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    n = len(matrix)
    px = max(64, int(round(size * dpr)))
    cell = max(1, px // (n + 6))
    offset = (px - cell * n) // 2
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#FFFFFF"))
    p.drawRoundedRect(QRectF(0, 0, px, px), px * 0.08, px * 0.08)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    p.setBrush(QColor("#000000"))
    for r, row in enumerate(matrix):
        for c, on in enumerate(row):
            if on:
                p.drawRect(offset + c * cell, offset + r * cell, cell, cell)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    badge = cell * n * 0.22
    centre = QPointF(px / 2, px / 2)
    pad = cell * 0.8
    p.setBrush(QColor("#FFFFFF"))
    p.drawRoundedRect(QRectF(centre.x() - badge / 2 - pad, centre.y() - badge / 2 - pad,
                             badge + 2 * pad, badge + 2 * pad), badge * 0.3, badge * 0.3)
    g = QLinearGradient(centre.x() - badge / 2, centre.y() - badge / 2,
                        centre.x() + badge / 2, centre.y() + badge / 2)
    g.setColorAt(0, QColor(BLUE))
    g.setColorAt(1, QColor(CYAN))
    p.setBrush(g)
    p.drawRoundedRect(QRectF(centre.x() - badge / 2, centre.y() - badge / 2, badge, badge),
                      badge * 0.25, badge * 0.25)
    draw_receive_glyph(p, centre, badge * 0.28, QColor("white"))
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def file_kind(name: str) -> tuple[str, str]:
    ext = Path(name).suffix.lower()
    if ext in IMAGE_EXT:
        return "IMG", BLUE
    if ext in VIDEO_EXT:
        return "VID", "#BF5AF2"
    if ext in AUDIO_EXT:
        return "AUD", "#FF375F"
    if ext in DOC_EXT:
        return "DOC", ORANGE
    if ext in ARCHIVE_EXT:
        return "ZIP", "#8E8E93"
    return "FILE", "#636366"


def placeholder_pixmap(name: str, size: int, dpr: float) -> QPixmap:
    label, color = file_kind(name)
    px = int(size * dpr)
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    base = QColor(color)
    g = QLinearGradient(0, 0, px, px)
    g.setColorAt(0, base.lighter(115))
    g.setColorAt(1, base.darker(135))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(g)
    p.drawRoundedRect(QRectF(0, 0, px, px), px * 0.22, px * 0.22)
    text = Path(name).suffix[1:].upper()[:4] or label
    font = QFont(FONT_FAMILY)
    font.setPixelSize(max(8, int(px * 0.24)))
    font.setBold(True)
    p.setFont(font)
    p.setPen(QColor("white"))
    p.drawText(QRectF(0, 0, px, px), Qt.AlignmentFlag.AlignCenter, text)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def rounded_pixmap(img: QImage, size: int, dpr: float) -> QPixmap:
    px = int(size * dpr)
    scaled = img.scaled(px, px, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation)
    cropped = scaled.copy((scaled.width() - px) // 2, (scaled.height() - px) // 2, px, px)
    out = QPixmap(px, px)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, px, px), px * 0.22, px * 0.22)
    p.setClipPath(path)
    p.drawImage(0, 0, cropped)
    p.end()
    out.setDevicePixelRatio(dpr)
    return out


def load_thumbnail(path: str, size: int, dpr: float) -> Optional[QPixmap]:
    try:
        if os.path.getsize(path) > 80 * 1024 * 1024:
            return None
    except OSError:
        return None
    target = int(size * dpr) * 2
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    if reader.canRead():
        src = reader.size()
        if src.isValid() and (src.width() > target or src.height() > target):
            reader.setScaledSize(src.scaled(target, target, Qt.AspectRatioMode.KeepAspectRatioByExpanding))
        img = reader.read()
        if not img.isNull():
            return rounded_pixmap(img, size, dpr)
    if Path(path).suffix.lower() in {".heic", ".heif"}:
        try:
            import pillow_heif
            from PIL import Image
            pillow_heif.register_heif_opener()
            with Image.open(path) as im:
                im.thumbnail((target, target))
                im = im.convert("RGBA")
                qimg = QImage(im.tobytes("raw", "RGBA"), im.width, im.height,
                              QImage.Format.Format_RGBA8888).copy()
            return rounded_pixmap(qimg, size, dpr)
        except Exception:
            pass
    return None


def make_toast_preview(path: str) -> Optional[str]:
    try:
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        src = reader.size()
        if src.isValid() and (src.width() > 728 or src.height() > 728):
            reader.setScaledSize(src.scaled(728, 728, Qt.AspectRatioMode.KeepAspectRatio))
        img = reader.read()
        if img.isNull():
            return None
        out = backend.app_data_dir() / f"toast_preview_{next(_preview_seq) % 4}.png"
        return str(out) if img.save(str(out), "PNG") else None
    except Exception:
        return None


# ───────────────────────── thread bridge & notifications ─────────────────────────
class Bridge(QObject):
    started = pyqtSignal(str, str, object)
    progress = pyqtSignal(str, object)
    done = pyqtSignal(str, str, object)
    failed = pyqtSignal(str, str)
    outbox_downloaded = pyqtSignal(str, int)
    mdns_result = pyqtSignal(bool, str)
    toast_clicked = pyqtSignal(str)

    def on_start(self, tid: str, name: str, total: int) -> None:
        self.started.emit(tid, name, total)

    def on_progress(self, tid: str, received: int) -> None:
        self.progress.emit(tid, received)

    def on_done(self, tid: str, path: str, size: int) -> None:
        self.done.emit(tid, path, size)

    def on_error(self, tid: str, message: str) -> None:
        self.failed.emit(tid, message)

    def on_outbox_download(self, oid: str, count: int) -> None:
        self.outbox_downloaded.emit(oid, count)


class Notifier:
    def __init__(self, bridge: Bridge):
        self._bridge = bridge
        self._toaster = None
        if os.name != "nt":
            return
        try:
            from windows_toasts import WindowsToaster
            self._toaster = WindowsToaster(backend.APP_NAME)
        except Exception:
            log.info("windows-toasts unavailable - falling back to tray balloons")

    def show(self, title: str, body: str, image: Optional[str], target: str) -> bool:
        if self._toaster is None:
            return False
        try:
            from windows_toasts import Toast, ToastDisplayImage, ToastImagePosition
            toast = Toast()
            toast.text_fields = [title, body]
            if image:
                try:
                    toast.AddImage(ToastDisplayImage.fromPath(image, position=ToastImagePosition.Hero))
                except Exception:
                    log.debug("Toast image skipped", exc_info=True)
            toast.on_activated = lambda _args, t=target: self._bridge.toast_clicked.emit(t)
            self._toaster.show_toast(toast)
            return True
        except Exception:
            log.exception("Toast failed")
            return False


# ───────────────────────── widgets ─────────────────────────
class ElidedLabel(QLabel):
    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._full = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self, text: str) -> None:
        self._full = text
        self.setToolTip(text)
        self._apply()

    def _apply(self) -> None:
        full = getattr(self, "_full", "")
        super().setText(self.fontMetrics().elidedText(full, Qt.TextElideMode.ElideMiddle,
                                                      max(20, self.width())))

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._apply()

    def changeEvent(self, e) -> None:
        super().changeEvent(e)
        if e.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._apply()


class RadarWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(200, 170)
        self._active = False
        self._speed = 1.0
        self._phase = 0.0
        self._last = time.monotonic()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def set_active(self, active: bool) -> None:
        self._active = active

    def _tick(self) -> None:
        now = time.monotonic()
        dt, self._last = now - self._last, now
        target = 2.2 if self._active else 1.0
        self._speed += (target - self._speed) * min(1.0, dt * 3)
        self._phase = (self._phase + dt * self._speed / 3.2) % 1.0
        if self.isVisible() and not self.window().isMinimized():
            self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        c = QPointF(w / 2, h / 2)
        r_max = min(w, h) / 2 - 6
        core = max(30.0, min(54.0, r_max * 0.32))
        if self._active:
            core *= 1 + 0.025 * (1 + math.sin(self._phase * math.tau * 3))
        accent = QColor(CYAN) if self._active else QColor(BLUE)

        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 12), 1))
        for f in (0.55, 0.78, 1.0):
            r = core + (r_max - core) * f
            p.drawEllipse(c, r, r)

        for i in range(3):
            ph = (self._phase + i / 3) % 1.0
            eased = 1 - (1 - ph) ** 3
            r = core + (r_max - core) * eased
            a = (1 - ph) ** 1.8
            stroke, fill = QColor(accent), QColor(accent)
            stroke.setAlphaF(0.6 * a)
            fill.setAlphaF(0.06 * a)
            p.setPen(QPen(stroke, 2))
            p.setBrush(fill)
            p.drawEllipse(c, r, r)

        glow = QRadialGradient(c, core * 2.0)
        g0, g1 = QColor(accent), QColor(accent)
        g0.setAlphaF(0.35)
        g1.setAlphaF(0.0)
        glow.setColorAt(0, g0)
        glow.setColorAt(1, g1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(c, core * 2.0, core * 2.0)

        grad = QLinearGradient(c.x() - core, c.y() - core, c.x() + core, c.y() + core)
        grad.setColorAt(0, QColor(BLUE))
        grad.setColorAt(1, QColor(CYAN))
        p.setBrush(grad)
        p.drawEllipse(c, core, core)
        hl = QLinearGradient(c.x(), c.y() - core, c.x(), c.y())
        hl.setColorAt(0, QColor(255, 255, 255, 60))
        hl.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(hl)
        p.drawEllipse(c, core * 0.94, core * 0.94)
        draw_receive_glyph(p, c, core * 0.42, QColor("white"))
        p.end()


class TransferItem(QFrame):
    THUMB = 44

    def __init__(self, tid: str, name: str, total: int, dpr: float):
        super().__init__()
        self.setObjectName("TransferItem")
        self.tid, self.total, self._dpr = tid, int(total or 0), dpr
        self.state = "active"
        self.path: Optional[str] = None
        self._t, self._b, self._speed = time.monotonic(), 0, 0.0

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(12)
        self.thumb = QLabel()
        self.thumb.setFixedSize(self.THUMB, self.THUMB)
        self.thumb.setPixmap(placeholder_pixmap(name, self.THUMB, dpr))
        lay.addWidget(self.thumb)

        col = QVBoxLayout()
        col.setSpacing(5)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.title = ElidedLabel(name)
        self.title.setObjectName("ItemTitle")
        self.size_label = QLabel(human(self.total) if self.total else "")
        self.size_label.setObjectName("Caption")
        top.addWidget(self.title, 1)
        top.addWidget(self.size_label)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(4)
        self.bar.setRange(0, 1000 if self.total else 0)
        self.status = QLabel("Starting…")
        self.status.setObjectName("Caption")
        col.addLayout(top)
        col.addWidget(self.bar)
        col.addWidget(self.status)
        lay.addLayout(col, 1)

        self.show_btn = QPushButton("Show")
        self.show_btn.setObjectName("Ghost")
        self.show_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.show_btn.clicked.connect(lambda: reveal_in_explorer(self.path or ""))
        self.show_btn.hide()
        lay.addWidget(self.show_btn)

    def set_progress(self, received: int) -> None:
        now = time.monotonic()
        dt = now - self._t
        if dt >= 0.25:
            inst = (received - self._b) / dt
            self._speed = inst if self._speed == 0 else self._speed * 0.7 + inst * 0.3
            self._t, self._b = now, received
        if self.total:
            self.bar.setValue(int(min(1.0, received / self.total) * 1000))
            text = f"{human(min(received, self.total))} of {human(self.total)}"
        else:
            text = human(received)
        if self._speed > 0:
            text += f"  ·  {human(self._speed)}/s"
            if self.total and self.total > received:
                text += f"  ·  {fmt_eta((self.total - received) / self._speed)}"
        self.status.setText(text)

    def set_done(self, path: str, size: int) -> None:
        self.state, self.path = "done", path
        self.bar.setRange(0, 1000)
        self.bar.setValue(1000)
        repolish(self.bar, state="done")
        self.title.setText(Path(path).name)
        self.size_label.setText(human(size))
        self.status.setText(f"Saved to {Path(path).parent.name}  ·  double-click to open")
        repolish(self.status, tone="ok")
        if Path(path).suffix.lower() in IMAGE_EXT:
            pm = load_thumbnail(path, self.THUMB, self._dpr)
            if pm:
                self.thumb.setPixmap(pm)
        self.show_btn.show()
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_failed(self, message: str) -> None:
        self.state = "error"
        self.bar.setRange(0, 1000)
        self.bar.setValue(1000)
        repolish(self.bar, state="error")
        self.status.setText(f"Failed — {message}")
        repolish(self.status, tone="err")

    def mouseDoubleClickEvent(self, e) -> None:
        if self.state == "done" and self.path:
            open_with_default_app(self.path)
        super().mouseDoubleClickEvent(e)


class OutboxItem(QFrame):
    THUMB = 44
    remove_requested = pyqtSignal(str)

    def __init__(self, oid: str, path: str, size: int, dpr: float):
        super().__init__()
        self.setObjectName("TransferItem")
        self.oid, self.path = oid, path
        self.setToolTip(path)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(12)
        thumb = QLabel()
        thumb.setFixedSize(self.THUMB, self.THUMB)
        pm = load_thumbnail(path, self.THUMB, dpr) if Path(path).suffix.lower() in IMAGE_EXT else None
        thumb.setPixmap(pm or placeholder_pixmap(path, self.THUMB, dpr))
        lay.addWidget(thumb)

        col = QVBoxLayout()
        col.setSpacing(5)
        top = QHBoxLayout()
        top.setSpacing(8)
        title = ElidedLabel(Path(path).name)
        title.setObjectName("ItemTitle")
        size_label = QLabel(human(size))
        size_label.setObjectName("Caption")
        top.addWidget(title, 1)
        top.addWidget(size_label)
        self.status = QLabel("Waiting · open the AirDrop page on your iPhone")
        self.status.setObjectName("Caption")
        col.addLayout(top)
        col.addWidget(self.status)
        lay.addLayout(col, 1)

        remove = QPushButton("Remove")
        remove.setObjectName("Ghost")
        remove.setCursor(Qt.CursorShape.PointingHandCursor)
        remove.clicked.connect(lambda: self.remove_requested.emit(self.oid))
        lay.addWidget(remove)

    def set_downloads(self, count: int) -> None:
        self.status.setText("Downloaded to iPhone" + (f"  ·  {count}×" if count > 1 else ""))
        repolish(self.status, tone="ok")

    def mouseDoubleClickEvent(self, e) -> None:
        reveal_in_explorer(self.path)
        super().mouseDoubleClickEvent(e)


class ListPanel(QScrollArea):
    def __init__(self, empty_text: str):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QWidget()
        self._lay = QVBoxLayout(host)
        self._lay.setContentsMargins(0, 4, 6, 0)
        self._lay.setSpacing(8)
        self.empty = QLabel(empty_text)
        self.empty.setObjectName("Caption")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        self.empty.setMinimumHeight(70)
        self._lay.addWidget(self.empty)
        self._lay.addStretch(1)
        self.setWidget(host)

    def add_top(self, w: QWidget) -> None:
        self._lay.insertWidget(1, w)
        self._sync()
        self.verticalScrollBar().setValue(0)

    def remove(self, w: QWidget) -> None:
        self._lay.removeWidget(w)
        w.hide()
        w.deleteLater()
        self._sync()

    def _sync(self) -> None:
        self.empty.setVisible(self._lay.count() <= 2)


class StatusPill(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("Pill")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 12, 4)
        lay.setSpacing(7)
        self.dot = QLabel()
        self.dot.setFixedSize(8, 8)
        self.text = QLabel()
        self.text.setObjectName("PillText")
        lay.addWidget(self.dot)
        lay.addWidget(self.text)

    def set(self, text: str, color: str) -> None:
        self.dot.setStyleSheet(f"background:{color}; border-radius:4px;")
        self.text.setText(text)


class SegmentedControl(QFrame):
    changed = pyqtSignal(int)

    def __init__(self, labels: list[str]):
        super().__init__()
        self.setObjectName("Segmented")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(2)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: list[QPushButton] = []
        for i, text in enumerate(labels):
            b = QPushButton(text)
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            self.group.addButton(b, i)
            lay.addWidget(b)
            self.buttons.append(b)
        self.buttons[0].setChecked(True)
        self.group.idClicked.connect(self.changed.emit)

    def set_index(self, i: int) -> None:
        self.buttons[i].setChecked(True)
        self.changed.emit(i)

    def set_label(self, i: int, text: str) -> None:
        self.buttons[i].setText(text)


class TitleBar(QWidget):
    def __init__(self, window: "MainWindow"):
        super().__init__(window)
        self.setFixedHeight(48)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 0, 16, 0)
        lay.setSpacing(8)
        for color, tip, slot in (("#FF5F57", "Close to tray", window.close),
                                 ("#FEBC2E", "Minimise", window.showMinimized)):
            b = QPushButton()
            b.setFixedSize(13, 13)
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"QPushButton{{background:{color};border-radius:6px;}}"
                            f"QPushButton:hover{{border:1px solid rgba(0,0,0,0.35);}}")
            b.clicked.connect(slot)
            lay.addWidget(b)
        idle = QLabel()
        idle.setFixedSize(13, 13)
        idle.setStyleSheet(f"background:{BORDER}; border-radius:6px;")
        lay.addWidget(idle)
        lay.addStretch(1)
        title = QLabel(backend.APP_NAME)
        title.setObjectName("WindowTitle")
        lay.addWidget(title)
        lay.addStretch(1)
        self.pill = StatusPill()
        lay.addWidget(self.pill)

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle:
                handle.startSystemMove()


# ───────────────────────── main window ─────────────────────────
class MainWindow(QWidget):
    SHADOW = 18
    RADIUS = 18
    QR_SIZE = 168

    def __init__(self, cfg: backend.Config, ip: str, port: int, outbox: backend.Outbox,
                 bridge: Bridge, advertiser: backend.MDNSAdvertiser):
        super().__init__()
        self.cfg, self.ip, self.port = cfg, ip, port
        self.outbox, self.bridge, self.advertiser = outbox, bridge, advertiser
        self.items: dict[str, TransferItem] = {}
        self.out_items: dict[str, OutboxItem] = {}
        self.tray: Optional[QSystemTrayIcon] = None
        self.allow_quit = False
        self._tray_hint_shown = False
        self._pending_toasts: list[str] = []
        self._dpr = QGuiApplication.primaryScreen().devicePixelRatio()
        self.notifier = Notifier(bridge)

        self.setWindowTitle(backend.APP_NAME)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
                            | Qt.WindowType.WindowMinimizeButtonHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAcceptDrops(True)
        self._fit_to_screen()

        outer = QVBoxLayout(self)
        s = self.SHADOW
        outer.setContentsMargins(s, s, s, s)
        self.root = QFrame()
        self.root.setObjectName("Root")
        outer.addWidget(self.root)
        rl = QVBoxLayout(self.root)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        self.titlebar = TitleBar(self)
        rl.addWidget(self.titlebar)
        body = QHBoxLayout()
        body.setContentsMargins(24, 4, 24, 22)
        body.setSpacing(24)
        rl.addLayout(body, 1)
        body.addLayout(self._build_main_column(), 1)
        body.addWidget(self._build_sidebar())

        bridge.started.connect(self._on_started)
        bridge.progress.connect(self._on_progress)
        bridge.done.connect(self._on_done)
        bridge.failed.connect(self._on_failed)
        bridge.outbox_downloaded.connect(self._on_outbox_downloaded)
        bridge.mdns_result.connect(self.set_mdns_status)
        bridge.toast_clicked.connect(self._on_toast_clicked)

        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.setInterval(1200)
        self._toast_timer.timeout.connect(self._flush_toasts)
        self._ip_timer = QTimer(self)
        self._ip_timer.setInterval(5000)
        self._ip_timer.timeout.connect(self._check_ip)
        self._ip_timer.start()

        self._setup_tray()
        self.set_ip(ip)

    def _fit_to_screen(self) -> None:
        avail = QGuiApplication.primaryScreen().availableGeometry()
        w = min(1000, avail.width() - 40) + 2 * self.SHADOW
        h = min(660, avail.height() - 40) + 2 * self.SHADOW
        self.resize(w, h)
        self.move(avail.center().x() - w // 2, avail.center().y() - h // 2)

    def _build_main_column(self) -> QVBoxLayout:
        v = QVBoxLayout()
        v.setSpacing(6)
        self.radar = RadarWidget()
        v.addWidget(self.radar, 4)
        self.h1 = QLabel("Ready to Receive")
        self.h1.setObjectName("H1")
        self.h1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub = QLabel("")
        self.sub.setObjectName("Sub")
        self.sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub.setWordWrap(True)
        v.addWidget(self.h1)
        v.addWidget(self.sub)
        v.addSpacing(12)

        head = QHBoxLayout()
        self.segment = SegmentedControl(["Received", "Send to iPhone"])
        self.segment.changed.connect(lambda i: self.stack.setCurrentIndex(i))
        add_btn = QPushButton("Add Files…")
        add_btn.setObjectName("Ghost")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setToolTip("Share files from this PC with your iPhone")
        add_btn.clicked.connect(self.choose_files)
        clear = QPushButton("Clear")
        clear.setObjectName("Link")
        clear.setCursor(Qt.CursorShape.PointingHandCursor)
        clear.clicked.connect(self.clear_current)
        head.addWidget(self.segment)
        head.addStretch(1)
        head.addWidget(add_btn)
        head.addWidget(clear)
        v.addLayout(head)

        self.stack = QStackedWidget()
        self.received_panel = ListPanel("Nothing yet — files you send from your iPhone will appear here.")
        self.outbox_panel = ListPanel("Drag files onto this window or click “Add Files…”.\n"
                                      "Your iPhone can then download them from the same AirDrop page.")
        self.stack.addWidget(self.received_panel)
        self.stack.addWidget(self.outbox_panel)
        v.addWidget(self.stack, 5)
        return v

    @staticmethod
    def _label(text: str, name: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName(name)
        return lbl

    def _build_sidebar(self) -> QWidget:
        side = QWidget()
        side.setFixedWidth(288)
        v = QVBoxLayout(side)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)

        card = QFrame()
        card.setObjectName("Card")
        q = QVBoxLayout(card)
        q.setContentsMargins(18, 16, 18, 16)
        q.setSpacing(8)
        title = self._label("Scan to Connect", "Section")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label = QLabel()
        self.qr_label.setFixedSize(self.QR_SIZE, self.QR_SIZE)
        cap = self._label("Point your iPhone Camera at this code, then tap the link.", "Caption")
        cap.setWordWrap(True)
        cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sep = QFrame()
        sep.setObjectName("Sep")
        q.addWidget(title)
        q.addWidget(self.qr_label, 0, Qt.AlignmentFlag.AlignHCenter)
        q.addWidget(cap)
        q.addWidget(sep)

        pin_row = QHBoxLayout()
        pin_row.addWidget(self._label("PAIRING PIN", "Overline"))
        pin_row.addStretch(1)
        pin = self.cfg.pin
        pin_row.addWidget(self._label(f"{pin[:3]} {pin[3:]}", "Pin"))
        q.addLayout(pin_row)
        q.addWidget(self._label("OR TYPE IN SAFARI", "Overline"))
        self.url_label = self._label("", "Mono")
        self.url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.mdns_label = self._label("", "Caption")
        self.mdns_label.setWordWrap(True)
        self.copy_btn = QPushButton("Copy Link")
        self.copy_btn.setObjectName("Ghost")
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.clicked.connect(self.copy_link)
        q.addWidget(self.url_label)
        q.addWidget(self.mdns_label)
        q.addWidget(self.copy_btn)
        v.addWidget(card)

        folder = QFrame()
        folder.setObjectName("Card")
        f = QVBoxLayout(folder)
        f.setContentsMargins(18, 14, 18, 14)
        f.setSpacing(6)
        f.addWidget(self._label("SAVED TO", "Overline"))
        path_label = ElidedLabel(self.cfg.save_dir)
        path_label.setObjectName("Caption")
        open_btn = QPushButton("Open Folder")
        open_btn.setObjectName("Primary")
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(self.open_folder)
        f.addWidget(path_label)
        f.addWidget(open_btn)
        v.addWidget(folder)
        v.addStretch(1)
        return side

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        s = self.SHADOW
        base = QRectF(self.rect()).adjusted(s, s, -s, -s)
        for i in range(s, 0, -2):
            alpha = int(36 * (1 - i / s) ** 2) + 2
            p.setBrush(QColor(0, 0, 0, alpha))
            p.drawRoundedRect(base.adjusted(-i, -i + 4, i, i + 4), self.RADIUS + i, self.RADIUS + i)
        p.end()

    def set_ip(self, ip: str) -> None:
        self.ip = ip
        base = f"http://{ip}:{self.port}"
        self.url_label.setText(base)
        self.qr_label.setPixmap(make_qr_pixmap(f"{base}/?pin={self.cfg.pin}", self.QR_SIZE, self._dpr))
        self._start_mdns()
        self._refresh_header()

    def _start_mdns(self) -> None:
        if self.ip.startswith("127."):
            self.set_mdns_status(False, "no network")
            return
        self.set_mdns_status(None, "")
        ip = self.ip

        def work() -> None:
            ok, text = self.advertiser.start(ip)
            self.bridge.mdns_result.emit(ok, text)

        threading.Thread(target=work, name="mdns", daemon=True).start()

    def set_mdns_status(self, ok: Optional[bool], text: str) -> None:
        if ok is None:
            self.mdns_label.setText(f"Publishing {backend.MDNS_HOSTNAME}.local…")
            repolish(self.mdns_label, tone="")
        elif ok:
            self.mdns_label.setText(f"Also works: http://{text}:{self.port}")
            repolish(self.mdns_label, tone="ok")
        else:
            self.mdns_label.setText("Bonjour name unavailable — use the IP link above.")
            repolish(self.mdns_label, tone="err")

    def _check_ip(self) -> None:
        ip = backend.get_local_ip()
        if ip != self.ip:
            log.info("IP changed %s -> %s", self.ip, ip)
            self.set_ip(ip)

    def _refresh_header(self) -> None:
        active = sum(1 for i in self.items.values() if i.state == "active")
        self.radar.set_active(active > 0)
        if active:
            self.h1.setText("Receiving…" if active == 1 else f"Receiving {active} files…")
            self.sub.setText("Keep Safari open on your iPhone until it finishes")
            pill = ("Receiving", CYAN)
        elif self.ip.startswith("127."):
            self.h1.setText("Not Connected")
            self.sub.setText("Connect this PC to the same Wi-Fi network as your iPhone")
            pill = ("Offline", ORANGE)
        else:
            self.h1.setText("Ready to Receive")
            self.sub.setText(f"Discoverable as “{self.cfg.device_name}”  ·  drop files here to send to iPhone")
            pill = ("Listening", GREEN)
        self.titlebar.pill.set(*pill)
        received = sum(1 for i in self.items.values() if i.state == "done")
        self.segment.set_label(0, f"Received  {received}" if received else "Received")
        n_out = len(self.out_items)
        self.segment.set_label(1, f"Send to iPhone  {n_out}" if n_out else "Send to iPhone")
        if self.tray:
            self.tray.setToolTip(f"{backend.APP_NAME} — {pill[0]}")

    def _on_started(self, tid: str, name: str, total) -> None:
        item = TransferItem(tid, name, int(total or 0), self._dpr)
        self.items[tid] = item
        self.received_panel.add_top(item)
        if self.stack.currentIndex() != 0:
            self.segment.set_index(0)
        self._refresh_header()

    def _on_progress(self, tid: str, received) -> None:
        item = self.items.get(tid)
        if item:
            item.set_progress(int(received))

    def _on_done(self, tid: str, path: str, size) -> None:
        item = self.items.get(tid)
        if item:
            item.set_done(path, int(size))
        self._pending_toasts.append(path)
        self._toast_timer.start()
        self._refresh_header()

    def _on_failed(self, tid: str, message: str) -> None:
        item = self.items.get(tid)
        if item:
            item.set_failed(message)
        self._refresh_header()

    def _flush_toasts(self) -> None:
        paths, self._pending_toasts = self._pending_toasts, []
        if not paths:
            return
        names = [Path(p).name for p in paths]
        if len(paths) == 1:
            title, body, target = "File received", names[0], paths[0]
        else:
            title = f"{len(paths)} files received"
            body = ", ".join(names[:3]) + (f" and {len(names) - 3} more" if len(names) > 3 else "")
            target = str(Path(paths[0]).parent)
        preview = next((p for p in paths if Path(p).suffix.lower() in TOAST_IMAGE_EXT), None)
        image = make_toast_preview(preview) if preview else None
        if not self.notifier.show(title, body, image, target) and self.tray:
            self.tray.showMessage(title, body, QSystemTrayIcon.MessageIcon.Information, 4000)

    def _on_toast_clicked(self, target: str) -> None:
        self.show_normal()
        if os.path.isfile(target):
            reveal_in_explorer(target)
        elif os.path.isdir(target):
            open_with_default_app(target)

    def choose_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Choose files to send to iPhone", str(Path.home()))
        if paths:
            self.add_outgoing(paths)

    def add_outgoing(self, paths: list[str]) -> None:
        skipped = 0
        for p in paths:
            try:
                item = self.outbox.add(Path(p))
            except OSError:
                skipped += 1
                continue
            if item.id in self.out_items:
                continue
            w = OutboxItem(item.id, str(item.path), item.size, self._dpr)
            w.remove_requested.connect(self.remove_outgoing)
            self.out_items[item.id] = w
            self.outbox_panel.add_top(w)
        self.segment.set_index(1)
        self._refresh_header()
        if skipped:
            QMessageBox.information(self, backend.APP_NAME,
                                    f"{skipped} item(s) skipped. Only files can be sent — "
                                    "zip folders first (right-click › Send to › Compressed folder).")

    def remove_outgoing(self, oid: str) -> None:
        self.outbox.remove(oid)
        w = self.out_items.pop(oid, None)
        if w:
            self.outbox_panel.remove(w)
        self._refresh_header()

    def _on_outbox_downloaded(self, oid: str, count: int) -> None:
        w = self.out_items.get(oid)
        if w:
            w.set_downloads(count)

    def clear_current(self) -> None:
        if self.stack.currentIndex() == 0:
            for tid, w in list(self.items.items()):
                if w.state != "active":
                    self.items.pop(tid)
                    self.received_panel.remove(w)
        else:
            self.outbox.clear()
            for w in self.out_items.values():
                self.outbox_panel.remove(w)
            self.out_items.clear()
        self._refresh_header()

    def dragEnterEvent(self, e) -> None:
        md = e.mimeData()
        if md.hasUrls() and any(u.isLocalFile() for u in md.urls()):
            e.acceptProposedAction()
            repolish(self.root, drop=True)

    def dragLeaveEvent(self, _e) -> None:
        repolish(self.root, drop=False)

    def dropEvent(self, e) -> None:
        repolish(self.root, drop=False)
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            e.acceptProposedAction()
            self.add_outgoing(paths)

    def copy_link(self) -> None:
        QGuiApplication.clipboard().setText(f"http://{self.ip}:{self.port}/?pin={self.cfg.pin}")
        self.copy_btn.setText("Copied ✓")
        QTimer.singleShot(1500, lambda: self.copy_btn.setText("Copy Link"))

    def open_folder(self) -> None:
        path = Path(self.cfg.save_dir)
        path.mkdir(parents=True, exist_ok=True)
        open_with_default_app(str(path))

    def show_normal(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(QApplication.windowIcon(), self)
        menu = QMenu()
        for text, slot in (("Open AirDrop PC", self.show_normal),
                           ("Send Files to iPhone…", lambda: (self.show_normal(), self.choose_files())),
                           ("Open Received Folder", self.open_folder),
                           ("Copy Link", self.copy_link)):
            act = QAction(text, menu)
            act.triggered.connect(slot)
            menu.addAction(act)
        menu.addSeparator()
        quit_act = QAction("Quit", menu)
        quit_act.triggered.connect(self.quit_app)
        menu.addAction(quit_act)
        self._tray_menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self.show_normal() if reason in (
                QSystemTrayIcon.ActivationReason.Trigger,
                QSystemTrayIcon.ActivationReason.DoubleClick) else None)
        self.tray.show()

    def quit_app(self) -> None:
        active = sum(1 for i in self.items.values() if i.state == "active")
        if active:
            answer = QMessageBox.question(self, backend.APP_NAME,
                                          f"{active} transfer(s) still in progress. Quit anyway?")
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.allow_quit = True
        if self.tray:
            self.tray.hide()
        QApplication.quit()

    def closeEvent(self, e) -> None:
        if self.allow_quit or self.tray is None:
            e.accept()
            if not self.allow_quit:
                self.allow_quit = True
                QTimer.singleShot(0, QApplication.quit)
            return
        e.ignore()
        self.hide()
        if not self._tray_hint_shown:
            self._tray_hint_shown = True
            self.tray.showMessage(backend.APP_NAME,
                                  "Still running in the background. Right-click the tray icon to quit.",
                                  QSystemTrayIcon.MessageIcon.Information, 3500)


# ───────────────────────── bootstrap ─────────────────────────
def setup_logging() -> Path:
    log_file = backend.app_data_dir() / "airdrop.log"
    handler = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    if sys.stderr is not None:
        root.addHandler(logging.StreamHandler())
    return log_file


def main() -> int:
    global FONT_FAMILY
    log_file = setup_logging()
    sys.excepthook = lambda t, v, tb: log.critical("Unhandled exception", exc_info=(t, v, tb))

    if os.name == "nt":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AirDropPC.App.1")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(backend.APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    FONT_FAMILY = pick_font_family()
    app.setFont(QFont(FONT_FAMILY, 10))
    app.setStyleSheet(QSS.replace("%FONT%", FONT_FAMILY))
    app.setWindowIcon(make_app_icon())

    lock = QLockFile(os.path.join(tempfile.gettempdir(), "AirDropPC.lock"))
    lock.setStaleLockTime(0)
    # ปรับตรงนี้: ถ้าโปรแกรมรันอยู่แล้ว ให้จบกระบวนการเงียบๆ ทันที ไม่ต้องเด้งกล่องข้อความเตือน
    if not lock.tryLock(200):
        return 0

    cfg = backend.Config.load()
    try:
        store = backend.FileStore(Path(cfg.save_dir))
    except OSError:
        log.exception("Save folder unusable - falling back to Downloads/AirDrop")
        cfg.save_dir = str(backend.windows_downloads_dir() / "AirDrop")
        cfg.save()
        store = backend.FileStore(Path(cfg.save_dir))

    try:
        port = backend.find_free_port(cfg.port)
    except RuntimeError as exc:
        QMessageBox.critical(None, backend.APP_NAME, str(exc))
        return 1
    if port != cfg.port:
        log.warning("Port %s busy - using %s", cfg.port, port)

    bridge = Bridge()
    outbox = backend.Outbox()
    server = backend.ServerThread(backend.create_app(cfg, bridge, store, outbox), port)
    server.start()
    if not server.wait_ready():
        QMessageBox.critical(None, backend.APP_NAME,
                             f"Could not start the local server on port {port}.\nDetails: {log_file}")
        return 1
    log.info("Server ready on port %s", port)

    advertiser = backend.MDNSAdvertiser(port, cfg.device_name)
    win = MainWindow(cfg, backend.get_local_ip(), port, outbox, bridge, advertiser)
    
    # ปรับตรงนี้: ปิด win.show() เพื่อให้เปิดตัวเงียบๆ ใน System Tray ทันทีตอนบูตเครื่อง
    # win.show()

    def shutdown() -> None:
        log.info("Shutting down")
        server.stop()
        advertiser.stop()

    app.aboutToQuit.connect(shutdown)
    code = app.exec()
    server.join(timeout=3)
    lock.unlock()
    return code


if __name__ == "__main__":
    sys.exit(main())