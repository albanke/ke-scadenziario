const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  onBadgeUpdate: (callback) => {
    ipcRenderer.on('badge-update', (_, data) => callback(data));
  },
  getBadgeCount: () => ipcRenderer.invoke('get-badge-count'),
  sendNotification: (title, body) => {
    ipcRenderer.send('notify', { title, body });
  },
  // Usato dal bottone "Testa" nelle impostazioni
  invoke: (channel, ...args) => {
    const allowed = ['send-test-notification'];
    if (allowed.includes(channel)) return ipcRenderer.invoke(channel, ...args);
    return Promise.reject(new Error('Channel non autorizzato: ' + channel));
  },
  openExternal: (url) => {
    ipcRenderer.send('open-external', url);
  },
  isElectron: true,
});
