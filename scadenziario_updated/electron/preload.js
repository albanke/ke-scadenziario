const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  onBadgeUpdate: (callback) => {
    ipcRenderer.on('badge-update', (_, data) => callback(data));
  },
  getBadgeCount: () => ipcRenderer.invoke('get-badge-count'),
  sendNotification: (title, body) => {
    ipcRenderer.send('notify', { title, body });
  },
  openExternal: (url) => {
    ipcRenderer.send('open-external', url);
  },
  isElectron: true,
});
