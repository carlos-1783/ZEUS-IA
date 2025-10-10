// preload.js
const { contextBridge, ipcRenderer } = require('electron')

// Expone las APIs seguras que necesitas en el frontend
contextBridge.exposeInMainWorld('electron', {
  // Aquí puedes exponer métodos seguros que necesites
})
