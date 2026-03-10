/**
 * KE Scadenziario — Electron Main Process
 * Badge su: 1) Taskbar Windows (overlay icona), 2) System tray, 3) Titolo finestra
 */

const { app, BrowserWindow, Notification, ipcMain, shell, Tray, Menu, nativeImage } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');
const { createCanvas } = (() => { try { return require('canvas'); } catch { return {}; } })();

const FLASK_PORT        = 5000;
const FLASK_URL         = `http://localhost:${FLASK_PORT}`;
const CHECK_INTERVAL_MS = 60 * 60 * 1000;
const STARTUP_DELAY_MS  = 3000;

let mainWindow  = null;
let tray        = null;
let flaskProc   = null;
let checkTimer  = null;
let lastBadge   = 0;

// ─────────────────────────────────────────────────────────────
//  Genera un'icona tray con il numero disegnato sopra (Canvas puro)
// ─────────────────────────────────────────────────────────────
function buildTrayIcon(count) {
  const SIZE = 16;

  // Costruiamo l'immagine pixel per pixel usando solo Electron nativeImage
  // Creiamo un SVG inline e lo convertiamo
  if (count <= 0) {
    // Icona normale: quadrato verde con "KE"
    return buildSvgIcon(null);
  }
  const label = count > 99 ? '99+' : String(count);
  return buildSvgIcon(label);
}

function buildSvgIcon(badgeText) {
  // SVG 16x16 — icona KE + badge rosso con numero
  const badge = badgeText ? `
    <circle cx="11" cy="5" r="5" fill="#F05A52"/>
    <text x="11" y="8.5" text-anchor="middle" font-family="Arial" font-weight="bold"
          font-size="${badgeText.length > 1 ? '4.5' : '6'}" fill="white">${badgeText}</text>
  ` : '';

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
    <!-- Sfondo verde -->
    <rect width="16" height="16" rx="3" fill="#4ECB74"/>
    <!-- Lettera K -->
    <text x="2" y="12" font-family="Arial Black,Arial" font-weight="900" font-size="10" fill="#0C1A0C">K</text>
    ${badge}
  </svg>`;

  const dataUrl = 'data:image/svg+xml;base64,' + Buffer.from(svg).toString('base64');
  return nativeImage.createFromDataURL(dataUrl);
}

// ─────────────────────────────────────────────────────────────
//  Overlay taskbar — quadratino rosso con numero (Windows)
// ─────────────────────────────────────────────────────────────
function buildOverlayIcon(count) {
  if (count <= 0) return null;
  const label = count > 99 ? '9+' : String(count);

  // SVG piccolo per overlay taskbar (mostra bene a 16x16 overlay)
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
    <circle cx="8" cy="8" r="8" fill="#F05A52"/>
    <text x="8" y="12" text-anchor="middle" font-family="Arial" font-weight="bold"
          font-size="${label.length > 1 ? '7' : '10'}" fill="white">${label}</text>
  </svg>`;

  const dataUrl = 'data:image/svg+xml;base64,' + Buffer.from(svg).toString('base64');
  return nativeImage.createFromDataURL(dataUrl);
}

// ─────────────────────────────────────────────────────────────
//  Flask
// ─────────────────────────────────────────────────────────────
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

function waitForFlask(cb, retries = 30) {
  http.get(`${FLASK_URL}/login`, res => {
    if (res.statusCode < 500) cb();
    else if (retries > 0) setTimeout(() => waitForFlask(cb, retries - 1), 500);
    else cb();
  }).on('error', () => {
    if (retries > 0) setTimeout(() => waitForFlask(cb, retries - 1), 500);
    else cb();
  });
}

// ─────────────────────────────────────────────────────────────
//  Finestra
// ─────────────────────────────────────────────────────────────
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

// ─────────────────────────────────────────────────────────────
//  Tray
// ─────────────────────────────────────────────────────────────
function createTray() {
  const icon = buildTrayIcon(0);
  tray = new Tray(icon);
  updateTrayMenu(0);
  tray.setToolTip('KE Scadenziario — caricamento...');
  tray.on('double-click', () => {
    if (mainWindow) { mainWindow.show(); mainWindow.focus(); }
    else createWindow();
  });
}

function updateTrayMenu(count) {
  const statusLabel = count > 0
    ? `⚠️  ${count} document${count > 1 ? 'i' : 'o'} da gestire`
    : '✅  Tutto in ordine';

  const menu = Menu.buildFromTemplate([
    { label: statusLabel, enabled: false },
    { type: 'separator' },
    { label: '📂  Apri KE Scadenziario', click: () => { if (mainWindow) { mainWindow.show(); mainWindow.focus(); } else createWindow(); } },
    { label: '🔄  Verifica scadenze ora', click: () => checkAndNotify() },
    { type: 'separator' },
    { label: '❌  Esci', click: () => app.quit() },
  ]);
  tray.setContextMenu(menu);
}

// ─────────────────────────────────────────────────────────────
//  Fetch docs — login + get documents con gestione cookie robusta
// ─────────────────────────────────────────────────────────────
let _sessionCookie = null; // cache della sessione per evitare login ripetuti

function doLogin() {
  return new Promise((resolve) => {
    const loginData = JSON.stringify({
      username: process.env.LOGIN_USERNAME || 'admin',
      password: process.env.LOGIN_PASSWORD || 'kegroup2024',
    });
    const loginReq = http.request({
      hostname: 'localhost', port: FLASK_PORT, path: '/api/login', method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(loginData),
      },
    }, loginRes => {
      // Raccogli tutti i Set-Cookie
      const raw = loginRes.headers['set-cookie'] || [];
      const cookie = raw.map(c => c.split(';')[0]).join('; ');
      resolve(cookie || null);
    });
    loginReq.on('error', () => resolve(null));
    loginReq.write(loginData);
    loginReq.end();
  });
}

function fetchWithCookie(cookie) {
  return new Promise((resolve) => {
    const opts = {
      hostname: 'localhost', port: FLASK_PORT, path: '/api/documents',
      headers: cookie ? { Cookie: cookie } : {},
    };
    const req = http.get(opts, res => {
      // Se 401 o redirect → sessione scaduta
      if (res.statusCode === 401 || res.statusCode === 302) { resolve(null); return; }
      let body = '';
      res.on('data', c => body += c);
      res.on('end', () => {
        try {
          const parsed = JSON.parse(body);
          resolve(Array.isArray(parsed) ? parsed : null);
        } catch { resolve(null); }
      });
    });
    req.on('error', () => resolve(null));
  });
}

async function fetchDocs() {
  // 1) Prova con cookie cached
  if (_sessionCookie) {
    const docs = await fetchWithCookie(_sessionCookie);
    if (docs !== null) return docs;
    // Cookie scaduto — fa nuovo login
    _sessionCookie = null;
  }
  // 2) Login fresco
  const cookie = await doLogin();
  if (!cookie) return [];
  _sessionCookie = cookie;
  const docs = await fetchWithCookie(cookie);
  return docs || [];
}

function getDocStatus(expiryDate) {
  const today = new Date(); today.setHours(0,0,0,0);
  const diff = Math.round((new Date(expiryDate) - today) / 86400000);
  if (diff < 0)   return { cls: 'crit', days: diff };
  if (diff <= 7)  return { cls: 'crit', days: diff };
  if (diff <= 30) return { cls: 'warn', days: diff };
  return { cls: 'ok', days: diff };
}

// ─────────────────────────────────────────────────────────────
//  CHECK + aggiorna TUTTI E TRE i badge
// ─────────────────────────────────────────────────────────────
async function checkAndNotify() {
  const docs = await fetchDocs();
  if (!Array.isArray(docs) || docs.length === 0) return;

  const expired  = docs.filter(d => getDocStatus(d.expiry_date).days < 0);
  const critical = docs.filter(d => { const s = getDocStatus(d.expiry_date); return s.days >= 0 && s.days <= 7; });
  const warning  = docs.filter(d => { const s = getDocStatus(d.expiry_date); return s.days > 7 && s.days <= 30; });
  const badgeCount = expired.length + critical.length;

  lastBadge = badgeCount;

  // ══ 1) TRAY ICON — disegna il numero sopra l'icona ══
  if (tray) {
    const trayIcon = buildTrayIcon(badgeCount);
    tray.setImage(trayIcon);
    const tip = badgeCount > 0
      ? `KE Scadenziario — ${badgeCount} document${badgeCount > 1 ? 'i' : 'o'} urgente${badgeCount > 1 ? 'i' : ''}`
      : 'KE Scadenziario — Tutto in ordine ✓';
    tray.setToolTip(tip);
    updateTrayMenu(badgeCount);
  }

  // ══ 2) TASKBAR OVERLAY — quadratino rosso con numero (Windows) ══
  if (process.platform === 'win32' && mainWindow && !mainWindow.isDestroyed()) {
    const overlay = buildOverlayIcon(badgeCount);
    const desc    = badgeCount > 0 ? `${badgeCount} scadenze` : '';
    mainWindow.setOverlayIcon(overlay, desc);

    // Flash taskbar se ci sono urgenze nuove
    if (badgeCount > 0) mainWindow.flashFrame(true);
  }

  // ══ 3) TITOLO FINESTRA — (N) KE Scadenziario ══
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.setTitle(badgeCount > 0 ? `(${badgeCount}) KE Scadenziario` : 'KE Scadenziario');
  }

  // ══ macOS dock badge ══
  if (process.platform === 'darwin' && app.dock) {
    app.dock.setBadge(badgeCount > 0 ? String(badgeCount) : '');
  }

  // ══ Notifiche desktop ══
  if (Notification.isSupported()) {
    if (expired.length > 0) {
      new Notification({
        title: `🚨 ${expired.length} document${expired.length > 1 ? 'i' : 'o'} scadut${expired.length > 1 ? 'i' : 'o'}!`,
        body: expired.slice(0, 3).map(d => `• ${d.name}`).join('\n') + (expired.length > 3 ? `\n+ altri ${expired.length - 3}…` : ''),
        icon: path.join(__dirname, 'icon.png'),
      }).show();
    }
    if (critical.length > 0) {
      new Notification({
        title: `⚠️ ${critical.length} scadenza${critical.length > 1 ? ' critiche' : ' critica'}`,
        body: critical.slice(0, 3).map(d => `• ${d.name} — tra ${getDocStatus(d.expiry_date).days}gg`).join('\n'),
        icon: path.join(__dirname, 'icon.png'),
      }).show();
    }
    if (warning.length > 0 && badgeCount === 0) {
      new Notification({
        title: `📋 ${warning.length} document${warning.length > 1 ? 'i' : 'o'} in scadenza entro 30gg`,
        body: warning.slice(0, 3).map(d => `• ${d.name} — ${getDocStatus(d.expiry_date).days}gg`).join('\n'),
        icon: path.join(__dirname, 'icon.png'),
      }).show();
    }
  }

  // ══ Notifica al renderer (badge in-app) ══
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('badge-update', {
      total: badgeCount, expired: expired.length,
      critical: critical.length, warning: warning.length,
    });
  }
}

// ─────────────────────────────────────────────────────────────
//  IPC
// ─────────────────────────────────────────────────────────────
ipcMain.handle('get-badge-count', async () => {
  const docs = await fetchDocs();
  if (!Array.isArray(docs)) return 0;
  return docs.filter(d => getDocStatus(d.expiry_date).days <= 7).length;
});

// Notifica nativa desktop — usata dal renderer via electronAPI.sendNotification
ipcMain.on('notify', (_, { title, body }) => {
  if (Notification.isSupported())
    new Notification({ title, body, icon: path.join(__dirname, 'icon.png') }).show();
});

// Handler per il test notifica dal renderer (invoke)
ipcMain.handle('send-test-notification', async () => {
  if (Notification.isSupported()) {
    new Notification({
      title: '🔔 KE Scadenziario — Test',
      body: 'Notifiche desktop attive e funzionanti!',
    }).show();
  }
  return true;
});

ipcMain.on('open-external', (_, url) => shell.openExternal(url));

// ─────────────────────────────────────────────────────────────
//  Lifecycle
// ─────────────────────────────────────────────────────────────
app.whenReady().then(() => {
  // Necessario su Windows per mostrare l'overlay taskbar
  app.setAppUserModelId('it.kegroup.scadenziario');

  startFlask();
  createTray();

  waitForFlask(() => {
    createWindow();
    setTimeout(checkAndNotify, STARTUP_DELAY_MS);
    checkTimer = setInterval(checkAndNotify, CHECK_INTERVAL_MS);
  });
});

app.on('window-all-closed', () => {
  // Non uscire — resta nel tray
});

app.on('activate', () => {
  if (!mainWindow) createWindow();
});

app.on('before-quit', () => {
  if (checkTimer) clearInterval(checkTimer);
  if (flaskProc)  flaskProc.kill();
  if (tray)       tray.destroy();
});
