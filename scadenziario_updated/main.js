/**
 * KE Scadenziario — Electron Preload
 * Bridge sicuro tra renderer (pagina web) e main process Electron
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Ricevi aggiornamenti badge dal main process
  onBadgeUpdate: (callback) => {
    ipcRenderer.on('badge-update', (_, data) => callback(data));
  },

  // Richiedi contatore badge corrente
  getBadgeCount: () => ipcRenderer.invoke('get-badge-count'),

  // Invia notifica desktop dal renderer
  sendNotification: (title, body) => {
    ipcRenderer.send('notify', { title, body });
  },

  // Apri link esterno
  openExternal: (url) => {
    ipcRenderer.send('open-external', url);
  },

  // Controlla se siamo in Electron
  isElectron: true,
});
