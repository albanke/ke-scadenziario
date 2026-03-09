{
  "name": "ke-scadenziario",
  "version": "2.0.0",
  "description": "KE Group — Registro Scadenze con notifiche desktop",
  "main": "electron/main.js",
  "scripts": {
    "start": "electron .",
    "build:win": "electron-builder --win",
    "build:mac": "electron-builder --mac",
    "build:linux": "electron-builder --linux"
  },
  "build": {
    "appId": "it.kegroup.scadenziario",
    "productName": "KE Scadenziario",
    "icon": "electron/icon.png",
    "directories": { "output": "dist" },
    "files": ["electron/**/*", "app.py", "templates/**/*", "requirements.txt"],
    "win": { "target": "nsis", "icon": "electron/icon.png" },
    "mac": { "target": "dmg", "icon": "electron/icon.icns" },
    "linux": { "target": "AppImage", "icon": "electron/icon.png" }
  },
  "devDependencies": {
    "electron": "^28.0.0",
    "electron-builder": "^24.0.0"
  },
  "author": "KE Group",
  "license": "UNLICENSED"
}
