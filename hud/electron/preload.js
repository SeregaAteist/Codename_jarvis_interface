'use strict'
/**
 * Preload — runs in isolated context between main and renderer.
 * Exposes a minimal, typed API via contextBridge.
 * Token is fetched once via IPC and cached as a plain string — safe to cross
 * the context boundary. The renderer performs its own fetch() so Response
 * objects stay in the renderer context (contextBridge cannot serialize them).
 */
const { contextBridge, ipcRenderer } = require('electron')

const BASE = 'http://127.0.0.1:7734'
let _token = null

async function getToken() {
  if (!_token) _token = await ipcRenderer.invoke('get-token')
  return _token
}

async function eventsUrl() {
  const t = await getToken()
  return `${BASE}/events?token=${encodeURIComponent(t)}`
}

contextBridge.exposeInMainWorld('jarvis', {
  getToken,
  eventsUrl,
})
