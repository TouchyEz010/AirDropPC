"""web_ui.py — iPhone Safari UI (Apple dark mode, AirDrop-style sheet). Served at GET /"""
import html


def render_index(device_name: str) -> str:
    return INDEX_HTML.replace("__DEVICE_NAME__", html.escape(device_name))


INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="dark">
<meta name="theme-color" content="#000000">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="AirDrop PC">
<meta name="format-detection" content="telephone=no">
<title>AirDrop PC</title>
<style>
:root{--bg:#000;--card:#1C1C1E;--card2:#2C2C2E;--line:#3A3A3C;--blue:#0A84FF;--cyan:#64D2FF;
--text:#F5F5F7;--sub:#8E8E93;--green:#30D158;--red:#FF453A;--orange:#FF9F0A}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html,body{min-height:100%;background:var(--bg);color:var(--text)}
body{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,sans-serif;font-size:17px;line-height:1.35;
-webkit-font-smoothing:antialiased;overflow-x:hidden;-webkit-user-select:none;user-select:none;
padding:calc(env(safe-area-inset-top) + 10px) 16px calc(env(safe-area-inset-bottom) + 18px);
background:radial-gradient(120% 55% at 50% 0%,#0b1a2e 0%,#000 62%) fixed}
.top{display:flex;align-items:center;justify-content:space-between;padding:6px 4px 14px}
.top h1{font-size:30px;font-weight:700;letter-spacing:-.5px}
.pill{display:flex;align-items:center;gap:7px;font-size:13px;font-weight:600;color:var(--text);background:rgba(44,44,46,.72);
border:1px solid rgba(58,58,60,.7);padding:6px 11px;border-radius:999px;-webkit-backdrop-filter:blur(20px);backdrop-filter:blur(20px)}
.pill i{width:8px;height:8px;border-radius:50%;background:var(--orange)}
.pill.ok i{background:var(--green);box-shadow:0 0 8px var(--green)}
.pill.bad i{background:var(--red)}
.sheet{position:relative;background:linear-gradient(180deg,rgba(44,44,46,.78),rgba(28,28,30,.78));border:1px solid rgba(58,58,60,.65);
border-radius:28px;padding:10px 20px 22px;display:flex;flex-direction:column;align-items:center;overflow:hidden;
-webkit-backdrop-filter:blur(30px) saturate(170%);backdrop-filter:blur(30px) saturate(170%);
box-shadow:0 24px 60px rgba(0,0,0,.55),inset 0 1px 0 rgba(255,255,255,.06)}
.grab{width:36px;height:5px;border-radius:3px;background:#48484A;margin-bottom:6px}
.radar{position:relative;width:240px;height:240px;display:grid;place-items:center;cursor:pointer;margin:4px 0;touch-action:manipulation}
.wave{position:absolute;left:50%;top:50%;width:116px;height:116px;margin:-58px 0 0 -58px;border-radius:50%;
border:1.5px solid rgba(100,210,255,.6);background:radial-gradient(circle,rgba(10,132,255,.10),transparent 70%);
opacity:0;animation:wave 3.6s cubic-bezier(.15,.6,.35,1) infinite}
.wave:nth-child(2){animation-delay:1.2s}.wave:nth-child(3){animation-delay:2.4s}
@keyframes wave{0%{transform:scale(.8);opacity:0}12%{opacity:1}100%{transform:scale(2.05);opacity:0}}
body.sending .wave{animation-duration:1.6s;border-color:rgba(100,210,255,.9)}
body.sending .wave:nth-child(2){animation-delay:.53s}body.sending .wave:nth-child(3){animation-delay:1.06s}
.ring{position:absolute;left:50%;top:50%;width:140px;height:140px;margin:-70px 0 0 -70px;transform:rotate(-90deg);opacity:0;transition:opacity .3s}
body.sending .ring,body.done .ring{opacity:1}
.ring circle{fill:none;stroke-width:5}
.ring .bg{stroke:rgba(255,255,255,.1)}
.ring .fg{stroke:url(#grad);stroke-linecap:round;transition:stroke-dashoffset .25s linear,stroke .3s}
body.done .ring .fg{stroke:var(--green)}
.avatar{position:relative;width:112px;height:112px;border-radius:50%;background:linear-gradient(145deg,#0A84FF,#64D2FF);
box-shadow:0 10px 30px rgba(10,132,255,.45),inset 0 1px 0 rgba(255,255,255,.35);transition:transform .25s cubic-bezier(.3,1.4,.5,1),background .35s}
.radar:active .avatar{transform:scale(.93)}
body.done .avatar{background:linear-gradient(145deg,#30D158,#34C759);box-shadow:0 10px 30px rgba(48,209,88,.45);animation:pop .5s cubic-bezier(.3,1.6,.5,1)}
body.error .avatar{background:linear-gradient(145deg,#FF453A,#FF6961);box-shadow:0 10px 30px rgba(255,69,58,.4)}
@keyframes pop{0%{transform:scale(.85)}60%{transform:scale(1.08)}100%{transform:scale(1)}}
.avatar svg{position:absolute;left:50%;top:50%;width:52px;height:52px;margin:-26px 0 0 -26px;transition:opacity .25s,transform .25s}
.pct{position:absolute;inset:0;display:grid;place-items:center;font-size:24px;font-weight:700;font-variant-numeric:tabular-nums;opacity:0;transition:opacity .25s}
.ic-check{opacity:0}
body.sending .ic-send,body.done .ic-send,body.error .ic-send{opacity:0;transform:scale(.6)}
body.sending .pct{opacity:1}
body.done .ic-check{opacity:1}
.ic-check path{stroke-dasharray:60;stroke-dashoffset:60}
body.done .ic-check path{animation:draw .5s .12s ease forwards}
@keyframes draw{to{stroke-dashoffset:0}}
.device{font-size:20px;font-weight:600;margin-top:4px;text-align:center;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hint{font-size:14px;color:var(--sub);margin-top:4px;text-align:center;min-height:19px;font-variant-numeric:tabular-nums}
.btn{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;height:52px;margin-top:18px;border:0;border-radius:14px;
background:var(--blue);color:#fff;font-family:inherit;font-size:17px;font-weight:600;cursor:pointer;transition:transform .15s,background .2s}
.btn:active{transform:scale(.97);background:#0071E3}
.btn:disabled{opacity:.5}
.picker{position:absolute;width:1px;height:1px;opacity:0;overflow:hidden;pointer-events:none}
.section{display:flex;justify-content:space-between;align-items:baseline;margin:26px 6px 10px}
.section h2{font-size:20px;font-weight:700}
.section button{background:none;border:0;color:var(--blue);font-size:15px;font-family:inherit}
.list{list-style:none;display:flex;flex-direction:column;gap:8px}
.row{display:flex;align-items:center;gap:12px;padding:10px 12px;background:rgba(28,28,30,.92);border:1px solid rgba(58,58,60,.55);
border-radius:16px;animation:rowIn .35s cubic-bezier(.2,.8,.2,1)}
@keyframes rowIn{from{opacity:0;transform:translateY(8px)}}
.thumb{width:46px;height:46px;flex:none;border-radius:11px;display:grid;place-items:center;overflow:hidden;font-size:11px;font-weight:700;color:#fff}
.thumb img{width:100%;height:100%;object-fit:cover}
.meta{flex:1;min-width:0}
.name{font-size:15px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sub{font-size:12.5px;color:var(--sub);margin-top:2px;font-variant-numeric:tabular-nums;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bar{height:4px;border-radius:2px;background:rgba(255,255,255,.08);margin-top:7px;overflow:hidden}
.bar i{display:block;height:100%;width:0;border-radius:2px;background:linear-gradient(90deg,var(--blue),var(--cyan));transition:width .2s linear}
.row.done .bar i{background:var(--green)}.row.error .bar i{background:var(--red)}
.act{width:30px;height:30px;flex:none;border:0;border-radius:50%;background:var(--card2);color:var(--sub);display:grid;place-items:center;font-size:15px;font-family:inherit}
.row.done .act{background:rgba(48,209,88,.15);color:var(--green)}
.row.error .act{background:rgba(255,69,58,.15);color:var(--red)}
.empty{color:var(--sub);font-size:14px;text-align:center;padding:18px 0}
.foot{color:#636366;font-size:12px;text-align:center;margin-top:22px;line-height:1.55}
.drop{position:fixed;inset:10px;display:grid;place-items:center;background:rgba(10,132,255,.18);border:3px dashed var(--cyan);border-radius:24px;
font-size:22px;font-weight:700;opacity:0;pointer-events:none;transition:opacity .2s;z-index:20;-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px)}
body.dragging .drop{opacity:1}
.modal{position:fixed;inset:0;background:rgba(0,0,0,.6);display:flex;align-items:flex-end;justify-content:center;opacity:0;pointer-events:none;
transition:opacity .25s;z-index:30;-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px)}
.modal.show{opacity:1;pointer-events:auto}
.modal .card{width:100%;max-width:480px;background:#1C1C1E;border:1px solid var(--line);border-radius:28px 28px 0 0;text-align:center;
padding:12px 22px calc(env(safe-area-inset-bottom) + 24px);transform:translateY(40px);transition:transform .35s cubic-bezier(.2,.9,.3,1)}
.modal.show .card{transform:none}
.modal h3{font-size:22px;margin:14px 0 6px}
.modal p{color:var(--sub);font-size:15px}
.pin{margin:20px auto 6px;width:100%;max-width:260px;height:58px;text-align:center;font-size:30px;letter-spacing:12px;font-weight:700;color:var(--text);
background:#000;border:1px solid var(--line);border-radius:14px;outline:none;font-family:inherit;-webkit-user-select:text;user-select:text}
.pin:focus{border-color:var(--blue);box-shadow:0 0 0 4px rgba(10,132,255,.25)}
.err{color:var(--red);font-size:14px;min-height:20px}
.toast{position:fixed;left:50%;bottom:calc(env(safe-area-inset-bottom) + 24px);transform:translate(-50%,30px);background:rgba(44,44,46,.94);
border:1px solid var(--line);padding:12px 18px;border-radius:999px;font-size:15px;font-weight:600;opacity:0;white-space:nowrap;z-index:40;
transition:all .35s cubic-bezier(.2,.9,.3,1);-webkit-backdrop-filter:blur(20px);backdrop-filter:blur(20px)}
.toast.show{opacity:1;transform:translate(-50%,0)}
@media (prefers-reduced-motion:reduce){.wave{animation:none}}
.tip{color:var(--sub);font-size:12.5px;margin:-4px 6px 10px;line-height:1.5}
.badge{display:inline-grid;place-items:center;min-width:22px;height:22px;padding:0 7px;margin-left:6px;border-radius:11px;
background:var(--blue);font-size:13px;font-weight:700;vertical-align:3px}
.acts{display:flex;gap:6px;flex:none}
.dl{display:grid;place-items:center;height:32px;padding:0 14px;border-radius:16px;background:var(--blue);color:#fff;
font-size:14px;font-weight:600;text-decoration:none;transition:transform .15s}
.dl:active{transform:scale(.94)}
.dl.secondary{background:var(--card2);color:var(--cyan)}
#inboxSec .row{animation:rowIn .35s cubic-bezier(.2,.8,.2,1)}
</style>
</head>
<body>
<header class="top">
  <h1>AirDrop</h1>
  <div class="pill" id="pill"><i></i><span id="pillText">Connecting…</span></div>
</header>

<main class="sheet">
  <div class="grab"></div>
  <label class="radar" for="files" aria-label="Choose files to send">
    <span class="wave"></span><span class="wave"></span><span class="wave"></span>
    <svg class="ring" viewBox="0 0 140 140" aria-hidden="true">
      <defs><linearGradient id="grad" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#0A84FF"/><stop offset="1" stop-color="#64D2FF"/></linearGradient></defs>
      <circle class="bg" cx="70" cy="70" r="64"/>
      <circle class="fg" id="ringFg" cx="70" cy="70" r="64"/>
    </svg>
    <div class="avatar">
      <svg class="ic-send" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/></svg>
      <svg class="ic-check" viewBox="0 0 52 52" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M14 27l8 8 16-17"/></svg>
      <span class="pct" id="pct">0%</span>
    </div>
  </label>
  <div class="device">__DEVICE_NAME__</div>
  <div class="hint" id="hint">Tap to send Photos, Videos or Files</div>
  <label class="btn" for="files">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
    Choose Files
  </label>
  <input class="picker" type="file" id="files" multiple>
</main>

<div class="section"><h2>Transfers</h2><button id="clearBtn" type="button" hidden>Clear</button></div>
<ul class="list" id="list"></ul>
<div class="empty" id="empty">Files you send will appear here.</div>
<section id="inboxSec" hidden>
  <div class="section"><h2>From PC<span class="badge" id="inboxCount">0</span></h2></div>
  <p class="tip"><b>Save</b> → Download = stored in <b>Files › Downloads</b>.<br>
  Photos: tap <b>Open</b>, then touch &amp; hold the image → <b>Save to Photos</b>.<br>
  Videos: <b>Save</b>, then open it in Files → Share → <b>Save Video</b>.</p>
  <ul class="list" id="inbox"></ul>
</section>
<p class="foot">Keep this page open until sending finishes.<br>Files are saved to <b>Downloads › AirDrop</b> on your PC.</p>

<div class="drop">Drop to send to PC</div>

<div class="modal" id="pinModal">
  <div class="card">
    <div class="grab" style="margin:0 auto"></div>
    <h3>Enter Pairing PIN</h3>
    <p>Type the 6-digit PIN shown on your PC.</p>
    <input class="pin" id="pinInput" type="text" inputmode="numeric" pattern="[0-9]*" maxlength="6" autocomplete="one-time-code" placeholder="••••••">
    <div class="err" id="pinErr"></div>
    <button class="btn" id="pinBtn" type="button">Connect</button>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const body = document.body, list = $('list'), ringFg = $('ringFg'), pct = $('pct'), hint = $('hint');
  const DEFAULT_HINT = hint.textContent, KEY = 'airdropPcPin', RING_C = 2 * Math.PI * 64;
  ringFg.style.strokeDasharray = RING_C; ringFg.style.strokeDashoffset = RING_C;

  let pin = '', authed = false, busy = false, seq = 0, resetTimer = 0, toastTimer = 0, wakeLock = null;
  const queue = [];
  const newBatch = () => ({ total: 0, done: 0, count: 0, ok: 0, fail: 0, cancelled: 0 });
  let batch = newBatch();

  const store = {
    get() { try { return localStorage.getItem(KEY) || ''; } catch (_) { return ''; } },
    set(v) { try { localStorage.setItem(KEY, v); } catch (_) {} },
    clear() { try { localStorage.removeItem(KEY); } catch (_) {} },
  };
  const fmt = (n) => {
    if (n < 1024) return Math.round(n) + ' B';
    const u = ['KB', 'MB', 'GB', 'TB']; let i = -1;
    do { n /= 1024; i++; } while (n >= 1024 && i < u.length - 1);
    return (n < 10 ? n.toFixed(1) : Math.round(n)) + ' ' + u[i];
  };
  const fmtEta = (s) => s < 60 ? Math.ceil(s) + ' s left' : s < 3600 ? Math.ceil(s / 60) + ' min left' : (s / 3600).toFixed(1) + ' h left';
  const kindColor = (f) => {
    const t = f.type || '';
    if (t.startsWith('image/')) return '#0A84FF';
    if (t.startsWith('video/')) return '#BF5AF2';
    if (t.startsWith('audio/')) return '#FF375F';
    if (/pdf|text|word|sheet|presentation/.test(t)) return '#FF9F0A';
    return '#48484A';
  };

  /* Haptics: navigator.vibrate is NOT available in iOS Safari.
     iOS 18+: toggling a native <input switch> fires a system haptic (best effort). */
  function haptic(times = 1) {
    if (navigator.vibrate) { navigator.vibrate(times > 1 ? [18, 70, 28] : 15); return; }
    for (let i = 0; i < times; i++) setTimeout(() => {
      try {
        const l = document.createElement('label'), c = document.createElement('input');
        c.type = 'checkbox'; c.setAttribute('switch', ''); l.appendChild(c);
        l.style.display = 'none'; document.body.appendChild(l); l.click(); l.remove();
      } catch (_) {}
    }, i * 130);
  }
  function toast(msg) {
    const t = $('toast'); t.textContent = msg; t.classList.add('show');
    clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove('show'), 2600);
  }
  function setPill(state, text) { $('pill').className = 'pill ' + state; $('pillText').textContent = text; }
  function setMode(mode) { body.classList.remove('sending', 'done', 'error'); if (mode !== 'idle') body.classList.add(mode); }
  function setRing(f) {
    f = Math.max(0, Math.min(1, f || 0));
    ringFg.style.strokeDashoffset = RING_C * (1 - f);
    pct.textContent = Math.floor(f * 100) + '%';
  }
  async function keepAwake(on) {   // Wake Lock needs HTTPS – silently ignored over plain HTTP
    try {
      if (on && 'wakeLock' in navigator && !wakeLock) {
        wakeLock = await navigator.wakeLock.request('screen');
        wakeLock.addEventListener('release', () => { wakeLock = null; });
      } else if (!on && wakeLock) { await wakeLock.release(); wakeLock = null; }
    } catch (_) {}
  }

  /* ---------- Rows ---------- */
  function makeRow(it) {
    const f = it.file;
    const li = document.createElement('li'); li.className = 'row';
    const th = document.createElement('div'); th.className = 'thumb'; th.style.background = kindColor(f);
    th.textContent = ((f.name.includes('.') ? f.name.split('.').pop() : '') || 'FILE').slice(0, 4).toUpperCase();
    if ((f.type || '').startsWith('image/') && f.size < 50 * 1024 * 1024) {
      const img = new Image(); img.alt = '';
      img.onload = () => { th.style.background = '#2C2C2E'; th.replaceChildren(img); };
      img.src = it.thumbUrl = URL.createObjectURL(f);
    }
    const meta = document.createElement('div'); meta.className = 'meta';
    const nm = document.createElement('div'); nm.className = 'name'; nm.textContent = f.name;
    const sub = document.createElement('div'); sub.className = 'sub';
    const bar = document.createElement('div'); bar.className = 'bar';
    const fill = document.createElement('i'); bar.appendChild(fill);
    meta.append(nm, sub, bar);
    const act = document.createElement('button'); act.className = 'act'; act.type = 'button';
    li.append(th, meta, act);
    it.ui = { li, sub, fill, act };
    renderRow(it);
    return li;
  }
  function renderRow(it) {
    const { li, sub, fill, act } = it.ui, size = it.file.size;
    const failed = it.state === 'error' || it.state === 'cancelled';
    li.className = 'row' + (it.state === 'done' ? ' done' : failed ? ' error' : '');
    act.disabled = false;
    if (it.state === 'queued' || it.state === 'sending') {
      act.textContent = '✕'; act.setAttribute('aria-label', 'Cancel'); act.onclick = () => cancel(it);
    } else if (it.state === 'done') {
      act.textContent = '✓'; act.disabled = true; act.onclick = null;
    } else {
      act.textContent = '↻'; act.setAttribute('aria-label', 'Retry'); act.onclick = () => retry(it);
    }
    if (it.state === 'queued') { sub.textContent = 'Waiting · ' + fmt(size); fill.style.width = '0%'; }
    else if (it.state === 'sending') {
      const f = size ? it.loaded / size : 0;
      fill.style.width = (f * 100).toFixed(1) + '%';
      let s = fmt(it.loaded) + ' of ' + fmt(size);
      if (it.speed > 0) {
        s += ' · ' + fmt(it.speed) + '/s';
        const eta = (size - it.loaded) / it.speed; if (eta > 1) s += ' · ' + fmtEta(eta);
      }
      sub.textContent = s;
    } else if (it.state === 'done') { fill.style.width = '100%'; sub.textContent = 'Sent · ' + fmt(size); }
    else { sub.textContent = it.state === 'cancelled' ? 'Cancelled' : 'Failed · ' + (it.error || 'Error'); }
  }
  function updateClear() {
    $('clearBtn').hidden = !queue.some((q) => ['done', 'error', 'cancelled'].includes(q.state));
    $('empty').hidden = queue.length > 0;
  }
  function updateOverall() {
    const cur = queue.find((q) => q.state === 'sending');
    setRing(batch.total ? (batch.done + (cur ? cur.loaded : 0)) / batch.total : 0);
  }

  /* ---------- Queue ---------- */
  function addFiles(files) {
    const arr = Array.from(files || []);
    if (!arr.length) return;
    clearTimeout(resetTimer);
    if (!busy && batch.count === 0) setRing(0);
    for (const f of arr) {
      const it = { id: ++seq, file: f, state: 'queued', loaded: 0, speed: 0 };
      list.appendChild(makeRow(it)); queue.push(it);
      batch.total += f.size; batch.count++;
    }
    updateClear(); haptic(1); pump();
  }
  function cancel(it) {
    if (it.state === 'sending' && it.xhr) { it.xhr.abort(); return; }
    if (it.state === 'queued') {
      it.state = 'cancelled'; batch.done += it.file.size; batch.cancelled++;
      renderRow(it); updateOverall(); updateClear(); if (!busy) pump();
    }
  }
  function retry(it) {
    clearTimeout(resetTimer);
    it.state = 'queued'; it.loaded = 0; it.speed = 0; it.error = '';
    batch.total += it.file.size; batch.count++;
    renderRow(it); updateClear(); pump();
  }
  function upload(it) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest(); it.xhr = xhr;
      let type = it.file.type || 'application/octet-stream';
      if (type.startsWith('multipart/')) type = 'application/octet-stream';
      xhr.open('POST', '/api/upload', true);
      xhr.setRequestHeader('X-PIN', pin);
      xhr.setRequestHeader('X-Filename', encodeURIComponent(it.file.name));
      xhr.setRequestHeader('Content-Type', type);
      let lastT = performance.now(), lastB = 0;
      xhr.upload.onprogress = (e) => {
        const now = performance.now();
        if (now - lastT > 400) {
          const inst = (e.loaded - lastB) / ((now - lastT) / 1000);
          it.speed = it.speed ? it.speed * 0.7 + inst * 0.3 : inst; lastT = now; lastB = e.loaded;
        }
        it.loaded = e.loaded; renderRow(it); updateOverall();
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) return resolve();
        let msg = 'HTTP ' + xhr.status;
        try { msg = JSON.parse(xhr.responseText).detail || msg; } catch (_) {}
        const err = new Error(msg); err.status = xhr.status; reject(err);
      };
      xhr.onerror = () => reject(new Error('Connection lost'));
      xhr.onabort = () => reject(new Error('Cancelled'));
      xhr.send(it.file);
    });
  }
  async function pump() {
    if (busy) return;
    const it = queue.find((q) => q.state === 'queued');
    if (!it) { finishBatch(); return; }
    if (!authed) { showPin(); return; }
    busy = true; clearTimeout(resetTimer); setMode('sending'); keepAwake(true);
    it.state = 'sending'; it.loaded = 0; it.speed = 0; renderRow(it);
    hint.textContent = 'Sending ' + (batch.ok + batch.fail + batch.cancelled + 1) + ' of ' + batch.count + '…';
    try {
      await upload(it); it.state = 'done'; batch.ok++;
    } catch (e) {
      it.xhr = null;
      if (e.status === 401) {                     // PIN changed on the PC
        it.state = 'queued'; renderRow(it); busy = false; authed = false; store.clear();
        showPin('PIN changed — please enter it again.'); return;
      }
      if (e.message === 'Cancelled') { it.state = 'cancelled'; batch.cancelled++; }
      else { it.state = 'error'; it.error = e.message; batch.fail++; }
    }
    it.xhr = null; batch.done += it.file.size;
    renderRow(it); updateOverall(); updateClear();
    busy = false; pump();
  }
  function finishBatch() {
    keepAwake(false);
    if (!batch.count) { setMode('idle'); return; }
    const { ok, fail } = batch;
    if (ok && !fail) { setRing(1); setMode('done'); haptic(2); hint.textContent = 'Done';
      toast(ok === 1 ? 'Sent to PC' : ok + ' items sent to PC'); }
    else if (ok) { setMode('done'); haptic(2); toast(ok + ' sent · ' + fail + ' failed'); }
    else if (fail) { setMode('error'); haptic(1); hint.textContent = 'Tap ↻ to retry'; toast('Sending failed'); }
    else { setMode('idle'); }
    batch = newBatch();
    resetTimer = setTimeout(() => {
      if (!busy) { setMode('idle'); setRing(0); hint.textContent = DEFAULT_HINT; }
    }, 2800);
  }

  /* ---------- PIN pairing ---------- */
  function showPin(msg) {
    $('pinErr').textContent = msg || ''; $('pinModal').classList.add('show');
    setTimeout(() => $('pinInput').focus(), 350);
  }
  function hidePin() { $('pinModal').classList.remove('show'); $('pinInput').blur(); }
  async function verify(p) {
    const r = await fetch('/api/verify', { method: 'POST', headers: { 'X-PIN': p }, cache: 'no-store' });
    if (r.ok) return true;
    if (r.status === 429) throw new Error('Too many attempts. Wait a minute and try again.');
    return false;
  }
  async function submitPin() {
    const v = $('pinInput').value.replace(/\D/g, '');
    if (v.length !== 6) { $('pinErr').textContent = 'PIN must be 6 digits'; return; }
    $('pinBtn').disabled = true;
    try {
      if (await verify(v)) {
        pin = v; authed = true; store.set(v); hidePin(); haptic(1);
        setPill('ok', 'Connected'); toast('Paired with PC'); pump();
      } else { $('pinErr').textContent = 'Incorrect PIN'; $('pinInput').select(); haptic(2); }
    } catch (e) {
      $('pinErr').textContent = e instanceof TypeError ? 'Cannot reach the PC' : e.message;
    } finally { $('pinBtn').disabled = false; }
  }
  $('pinBtn').addEventListener('click', submitPin);
  $('pinInput').addEventListener('input', (e) => {
    e.target.value = e.target.value.replace(/\D/g, '').slice(0, 6);
    if (e.target.value.length === 6) submitPin();
  });
  $('pinInput').addEventListener('keydown', (e) => { if (e.key === 'Enter') submitPin(); });

  /* ---------- Inputs: picker + drag & drop ---------- */
  $('files').addEventListener('change', (e) => { addFiles(e.target.files); e.target.value = ''; });
  $('clearBtn').addEventListener('click', () => {
    const keep = queue.filter((q) => q.state === 'queued' || q.state === 'sending');
    for (const q of queue) if (!keep.includes(q)) { q.ui.li.remove(); if (q.thumbUrl) URL.revokeObjectURL(q.thumbUrl); }
    queue.splice(0, queue.length, ...keep); updateClear();
  });
  const hasFiles = (e) => e.dataTransfer && Array.from(e.dataTransfer.types || []).includes('Files');
  let dragDepth = 0;
  addEventListener('dragenter', (e) => { if (hasFiles(e)) { e.preventDefault(); dragDepth++; body.classList.add('dragging'); } });
  addEventListener('dragover', (e) => { if (hasFiles(e)) { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; } });
  addEventListener('dragleave', () => { if (--dragDepth <= 0) { dragDepth = 0; body.classList.remove('dragging'); } });
  addEventListener('drop', (e) => {
    e.preventDefault(); dragDepth = 0; body.classList.remove('dragging');
    if (e.dataTransfer && e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
  });
  addEventListener('beforeunload', (e) => { if (busy) { e.preventDefault(); e.returnValue = ''; } });

  /* ---------- Connection status ---------- */
  async function ping() {
    if (busy) return;
    try {
      const r = await fetch('/api/info', { cache: 'no-store' });
      if (!r.ok) throw new Error();
      setPill(authed ? 'ok' : '', authed ? 'Connected' : 'Not paired');
    } catch (_) { setPill('bad', 'PC not reachable'); }
  }
  document.addEventListener('visibilitychange', () => { if (!document.hidden) ping(); });

  async function init() {
    const qp = new URLSearchParams(location.search);
    const fromUrl = (qp.get('pin') || '').replace(/\D/g, '');
    if (fromUrl) history.replaceState(null, '', location.pathname);   // hide PIN from the address bar
    const candidate = fromUrl || store.get();
    try {
      if (candidate && await verify(candidate)) {
        pin = candidate; authed = true; store.set(candidate); setPill('ok', 'Connected');
      } else {
        setPill('', 'Not paired');
        showPin(fromUrl ? 'This QR code is outdated — enter the PIN.' : '');
      }
    } catch (_) { setPill('bad', 'PC not reachable'); }
    setInterval(ping, 6000);
  }
  init();
})();
</script>
<script>
/* PC -> iPhone: shows files shared from the PC app ("Send to iPhone") */
(() => {
  'use strict';
  const KEY = 'airdropPcPin';
  const $ = (id) => document.getElementById(id);
  const sec = $('inboxSec'), list = $('inbox'), badge = $('inboxCount'), toastEl = $('toast');
  const rows = new Map();
  let version = null, lastPin = '', badPin = '', known = null, timer = 0;

  const getPin = () => { try { return localStorage.getItem(KEY) || ''; } catch (_) { return ''; } };
  const fileUrl = (id, pin, dl) =>
    '/api/outbox/' + encodeURIComponent(id) + '?pin=' + encodeURIComponent(pin) + (dl ? '&dl=1' : '');
  const fmt = (n) => {
    if (n < 1024) return n + ' B';
    const u = ['KB', 'MB', 'GB', 'TB']; let i = -1;
    do { n /= 1024; i++; } while (n >= 1024 && i < u.length - 1);
    return (n < 10 ? n.toFixed(1) : Math.round(n)) + ' ' + u[i];
  };
  const color = (m) => m.startsWith('image/') ? '#0A84FF' : m.startsWith('video/') ? '#BF5AF2'
    : m.startsWith('audio/') ? '#FF375F' : /pdf|text|word|sheet|presentation/.test(m) ? '#FF9F0A' : '#48484A';
  function flash(msg) {
    toastEl.textContent = msg; toastEl.classList.add('show');
    setTimeout(() => toastEl.classList.remove('show'), 2600);
  }

  function makeRow(it, pin) {
    const li = document.createElement('li'); li.className = 'row';
    const th = document.createElement('div'); th.className = 'thumb'; th.style.background = color(it.mime);
    th.textContent = ((it.name.includes('.') ? it.name.split('.').pop() : '') || 'FILE').slice(0, 4).toUpperCase();
    const isImg = it.mime.startsWith('image/'), isVid = it.mime.startsWith('video/');
    if (isImg && it.size < 20 * 1024 * 1024) {
      const img = new Image(); img.alt = ''; img.decoding = 'async'; img.loading = 'lazy';
      img.onload = () => { th.style.background = '#2C2C2E'; th.replaceChildren(img); };
      img.src = fileUrl(it.id, pin, false);
    }
    const meta = document.createElement('div'); meta.className = 'meta';
    const nm = document.createElement('div'); nm.className = 'name'; nm.textContent = it.name;
    const sub = document.createElement('div'); sub.className = 'sub'; sub.textContent = fmt(it.size) + ' · from PC';
    meta.append(nm, sub);
    const acts = document.createElement('div'); acts.className = 'acts';
    if (isImg || isVid) {
      const open = document.createElement('a'); open.className = 'dl secondary'; open.textContent = 'Open';
      open.href = fileUrl(it.id, pin, false); open.target = '_blank'; open.rel = 'noopener';
      acts.appendChild(open);
    }
    const save = document.createElement('a'); save.className = 'dl'; save.textContent = 'Save';
    save.href = fileUrl(it.id, pin, true); save.setAttribute('download', it.name);
    save.addEventListener('click', () => { sub.textContent = fmt(it.size) + ' · Downloading… see Safari downloads'; });
    acts.appendChild(save);
    li.append(th, meta, acts);
    return li;
  }

  function render(items, pin) {
    if (pin !== lastPin) { rows.clear(); list.replaceChildren(); lastPin = pin; }
    const ids = new Set(items.map((i) => i.id));
    for (const [id, li] of rows) if (!ids.has(id)) { li.remove(); rows.delete(id); }
    items.forEach((it, idx) => {
      let li = rows.get(it.id);
      if (!li) { li = makeRow(it, pin); rows.set(it.id, li); }
      if (list.children[idx] !== li) list.insertBefore(li, list.children[idx] || null);
    });
    if (known && items.some((i) => !known.has(i.id))) flash('New file from PC');
    known = ids;
    badge.textContent = items.length;
    sec.hidden = items.length === 0;
  }

  async function poll() {
    clearTimeout(timer);
    const pin = getPin();
    if (pin && pin !== badPin && !document.hidden) {
      try {
        const r = await fetch('/api/outbox', { headers: { 'X-PIN': pin }, cache: 'no-store' });
        if (r.status === 401) { badPin = pin; render([], pin); }      // stop: avoids PIN lock-out
        else if (r.ok) {
          const data = await r.json();
          if (data.version !== version || pin !== lastPin) { version = data.version; render(data.items, pin); }
        }
      } catch (_) { /* PC offline – retry */ }
    }
    timer = setTimeout(poll, 3000);
  }
  document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); });
  poll();
})();
</script>
</body>
</html>
"""