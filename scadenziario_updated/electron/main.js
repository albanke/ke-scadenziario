/**
 * KE Scadenziario — Electron Main Process
 */

const { app, BrowserWindow, Notification, ipcMain, shell, Tray, Menu, nativeImage } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

const FLASK_PORT        = 5000;
const FLASK_URL         = `http://localhost:${FLASK_PORT}`;
const CHECK_INTERVAL_MS = 60 * 60 * 1000; // ogni ora
const STARTUP_DELAY_MS  = 4000;

let mainWindow  = null;
let tray        = null;
let flaskProc   = null;
let checkTimer  = null;

// ── CRITICO per notifiche Windows 10/11 ──────────────────────────────────────
// Deve essere chiamato PRIMA di app.whenReady()
app.setAppUserModelId('it.kegroup.scadenziario');

// ── Icone SVG ─────────────────────────────────────────────────────────────────
function buildSvgIcon(badgeText) {
  const badge = badgeText ? `
    <circle cx="11" cy="5" r="5" fill="#F05A52"/>
    <text x="11" y="8.5" text-anchor="middle" font-family="Arial" font-weight="bold"
          font-size="${badgeText.length > 1 ? '4.5' : '6'}" fill="white">${badgeText}</text>
  ` : '';
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
    <rect width="16" height="16" rx="3" fill="#4ECB74"/>
    <text x="2" y="12" font-family="Arial Black,Arial" font-weight="900" font-size="10" fill="#0C1A0C">K</text>
    ${badge}
  </svg>`;
  return nativeImage.createFromDataURL('data:image/svg+xml;base64,' + Buffer.from(svg).toString('base64'));
}

function buildOverlayIcon(count) {
  if (count <= 0) return null;
  const label = count > 99 ? '99+' : String(count);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
    <circle cx="8" cy="8" r="8" fill="#F05A52"/>
    <text x="8" y="12" text-anchor="middle" font-family="Arial" font-weight="bold"
          font-size="${label.length > 1 ? '7' : '10'}" fill="white">${label}</text>
  </svg>`;
  return nativeImage.createFromDataURL('data:image/svg+xml;base64,' + Buffer.from(svg).toString('base64'));
}

// ── Flask ─────────────────────────────────────────────────────────────────────
function startFlask() {
  const scriptPath = path.join(__dirname, '..', 'app.py');
  const python = process.platform === 'win32' ? 'python' : 'python3';
  flaskProc = spawn(python, [scriptPath], {
    env: { ...process.env, FLASK_ENV: 'production', PORT: String(FLASK_PORT) },
    cwd: path.join(__dirname, '..'),
  });
  flaskProc.stdout.on('data', d => console.log('[Flask]', d.toString().trim()));
  flaskProc.stderr.on('data', d => console.error('[Flask ERR]', d.toString().trim()));
  flaskProc.on('close', code => console.log(`[Flask] exited ${code}`));
}

function waitForFlask(cb, retries = 60) {
  http.get(`${FLASK_URL}/login`, res => {
    if (res.statusCode < 500) cb();
    else if (retries > 0) setTimeout(() => waitForFlask(cb, retries - 1), 1000);
    else cb();
  }).on('error', () => {
    if (retries > 0) setTimeout(() => waitForFlask(cb, retries - 1), 1000);
    else cb();
  });
}

// ── Finestra ──────────────────────────────────────────────────────────────────
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280, height: 820, minWidth: 900, minHeight: 600,
    title: 'KE Scadenziario',
    backgroundColor: '#141C14',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    icon: buildSvgIcon(null),
    show: false,
  });

  mainWindow.loadURL(FLASK_URL);
  mainWindow.once('ready-to-show', () => mainWindow.show());
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith(FLASK_URL)) shell.openExternal(url);
    return { action: 'deny' };
  });
  mainWindow.on('closed', () => { mainWindow = null; });
}

// ── Tray ──────────────────────────────────────────────────────────────────────
function createTray() {
  tray = new Tray(buildSvgIcon(null));
  updateTray(0);
  tray.on('double-click', () => {
    if (mainWindow) { mainWindow.show(); mainWindow.focus(); }
    else createWindow();
  });
}

function updateTray(count) {
  if (!tray) return;
  const label = count > 99 ? '99+' : String(count);
  tray.setImage(buildSvgIcon(count > 0 ? label : null));
  tray.setToolTip(count > 0
    ? `KE Scadenziario — ${count} documento${count > 1 ? 'i' : ''} urgente${count > 1 ? 'i' : ''}`
    : 'KE Scadenziario — Tutto in ordine ✓');
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: count > 0 ? `⚠️  ${count} doc da gestire` : '✅  Tutto in ordine', enabled: false },
    { type: 'separator' },
    { label: '📂  Apri KE Scadenziario', click: () => {
      if (mainWindow) { mainWindow.show(); mainWindow.focus(); } else createWindow();
    }},
    { label: '🔄  Verifica scadenze ora', click: () => checkAndNotify() },
    { type: 'separator' },
    { label: '❌  Esci', click: () => app.quit() },
  ]));
}

// ── Fetch documenti ───────────────────────────────────────────────────────────
let _sessionCookie = null;

function doLogin() {
  return new Promise((resolve) => {
    const body = JSON.stringify({
      username: process.env.LOGIN_USERNAME || 'admin',
      password: process.env.LOGIN_PASSWORD || 'kegroup2024',
    });
    const req = http.request({
      hostname: 'localhost', port: FLASK_PORT, path: '/api/login', method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) },
    }, res => {
      // Consuma il body
      res.resume();
      const raw = res.headers['set-cookie'] || [];
      resolve(raw.map(c => c.split(';')[0]).join('; ') || null);
    });
    req.on('error', () => resolve(null));
    req.write(body);
    req.end();
  });
}

function fetchWithCookie(cookie) {
  return new Promise((resolve) => {
    const opts = {
      hostname: 'localhost', port: FLASK_PORT, path: '/api/documents',
      headers: cookie ? { Cookie: cookie } : {},
    };
    http.get(opts, res => {
      if (res.statusCode === 401 || res.statusCode === 302) { res.resume(); resolve(null); return; }
      let body = '';
      res.on('data', c => body += c);
      res.on('end', () => {
        try {
          const parsed = JSON.parse(body);
          resolve(Array.isArray(parsed) ? parsed : null);
        } catch { resolve(null); }
      });
    }).on('error', () => resolve(null));
  });
}

async function fetchDocs() {
  if (_sessionCookie) {
    const docs = await fetchWithCookie(_sessionCookie);
    if (docs !== null) return docs;
    _sessionCookie = null;
  }
  const cookie = await doLogin();
  if (!cookie) return [];
  _sessionCookie = cookie;
  return (await fetchWithCookie(cookie)) || [];
}

function getDocStatus(expiryDate) {
  const today = new Date(); today.setHours(0, 0, 0, 0);
  return Math.round((new Date(expiryDate) - today) / 86400000);
}

// ── CHECK + NOTIFICHE WINDOWS NATIVE ─────────────────────────────────────────
async function checkAndNotify() {
  const docs = await fetchDocs();
  if (!Array.isArray(docs) || docs.length === 0) return;

  const expired  = docs.filter(d => getDocStatus(d.expiry_date) < 0);
  const critical = docs.filter(d => { const x = getDocStatus(d.expiry_date); return x >= 0 && x <= 7; });
  const warning  = docs.filter(d => { const x = getDocStatus(d.expiry_date); return x > 7 && x <= 30; });
  const badgeCount = expired.length + critical.length;

  // ── 1) Tray icon con badge ──
  updateTray(badgeCount);

  // ── 2) Taskbar overlay Windows ──
  if (process.platform === 'win32' && mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.setOverlayIcon(buildOverlayIcon(badgeCount), badgeCount > 0 ? `${badgeCount} scadenze` : '');
    if (badgeCount > 0) mainWindow.flashFrame(true);
  }

  // ── 3) Titolo finestra ──
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.setTitle(badgeCount > 0 ? `(${badgeCount}) KE Scadenziario` : 'KE Scadenziario');
  }

  // ── 4) macOS dock badge ──
  if (process.platform === 'darwin' && app.dock) {
    app.dock.setBadge(badgeCount > 0 ? String(badgeCount) : '');
  }

  // ── 5) Notifiche desktop native ──
  //
  // Su Windows 10/11: Notification funziona se:
  //   a) app.setAppUserModelId è stato chiamato (fatto all'inizio)
  //   b) l'app è packaged (OPPURE in dev: toastActivatorCLSID non serve per info-level)
  //   c) le notifiche di sistema non sono disabilitate dall'utente nelle impostazioni Windows
  //
  if (Notification.isSupported()) {
    if (expired.length > 0) {
      const n = new Notification({
        title: `🚨 ${expired.length} documento${expired.length > 1 ? 'i' : ''} scaduto${expired.length > 1 ? 'i' : ''}!`,
        body: expired.slice(0, 3).map(d => `• ${d.name}`).join('\n') +
              (expired.length > 3 ? `\n+ altri ${expired.length - 3}…` : ''),
        urgency: 'critical',
        timeoutType: 'never',
      });
      n.on('click', () => { if (mainWindow) { mainWindow.show(); mainWindow.focus(); } });
      n.show();
    } else if (critical.length > 0) {
      const n = new Notification({
        title: `⚠️ ${critical.length} scadenza${critical.length > 1 ? ' critiche' : ' critica'}`,
        body: critical.slice(0, 3).map(d => `• ${d.name} — tra ${getDocStatus(d.expiry_date)}gg`).join('\n'),
        urgency: 'critical',
        timeoutType: 'never',
      });
      n.on('click', () => { if (mainWindow) { mainWindow.show(); mainWindow.focus(); } });
      n.show();
    } else if (warning.length > 0) {
      const n = new Notification({
        title: `📋 ${warning.length} documento${warning.length > 1 ? 'i' : ''} in scadenza entro 30gg`,
        body: warning.slice(0, 3).map(d => `• ${d.name} — ${getDocStatus(d.expiry_date)}gg`).join('\n'),
        urgency: 'normal',
      });
      n.on('click', () => { if (mainWindow) { mainWindow.show(); mainWindow.focus(); } });
      n.show();
    }
  }

  // ── 6) Badge in-app al renderer ──
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('badge-update', {
      total: badgeCount, expired: expired.length,
      critical: critical.length, warning: warning.length,
    });
  }
}

// ── IPC ───────────────────────────────────────────────────────────────────────
ipcMain.handle('get-badge-count', async () => {
  const docs = await fetchDocs();
  if (!Array.isArray(docs)) return 0;
  return docs.filter(d => getDocStatus(d.expiry_date) <= 7).length;
});

ipcMain.on('notify', (_, { title, body }) => {
  if (!Notification.isSupported()) return;
  const n = new Notification({ title, body, urgency: 'normal' });
  n.on('click', () => { if (mainWindow) { mainWindow.show(); mainWindow.focus(); } });
  n.show();
});

ipcMain.handle('send-test-notification', async () => {
  if (!Notification.isSupported()) return false;
  const n = new Notification({
    title: '🔔 KE Scadenziario',
    body: 'Notifiche desktop Windows attive e funzionanti!',
    urgency: 'normal',
  });
  n.on('click', () => { if (mainWindow) { mainWindow.show(); mainWindow.focus(); } });
  n.show();
  return true;
});

ipcMain.on('open-external', (_, url) => shell.openExternal(url));

// ── Lifecycle ─────────────────────────────────────────────────────────────────
app.whenReady().then(() => {
  startFlask();
  createTray();

  waitForFlask(() => {
    createWindow();
    setTimeout(checkAndNotify, STARTUP_DELAY_MS);
    checkTimer = setInterval(checkAndNotify, CHECK_INTERVAL_MS);
  });
});

app.on('window-all-closed', () => {
  // Rimane nel tray — non esce
});

app.on('activate', () => {
  if (!mainWindow) createWindow();
});

app.on('before-quit', () => {
  if (checkTimer) clearInterval(checkTimer);
  if (flaskProc)  flaskProc.kill();
  if (tray)       tray.destroy();
});
