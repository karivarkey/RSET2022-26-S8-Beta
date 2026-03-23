// See the Electron documentation for details on how to use preload scripts:
// https://www.electronjs.org/docs/latest/tutorial/process-model#preload-scripts


const { contextBridge, ipcRenderer } = require('electron')
contextBridge.exposeInMainWorld('electronAPI', {
  minimize: () => ipcRenderer.send('window:minimize'),
  close: () => ipcRenderer.send('window:close'),
    toggleAlwaysOnTop: () => ipcRenderer.send('window:toggle-always-on-top'),
     resetToRightmost: () => ipcRenderer.send('window:reset-rightmost'),  
})


