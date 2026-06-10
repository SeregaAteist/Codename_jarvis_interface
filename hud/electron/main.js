const { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain } = require('electron')
const { spawn }      = require('child_process')
const { randomUUID } = require('crypto')
const net            = require('net')
const path           = require('path')
const os             = require('os')

// ── SINGLE INSTANCE LOCK ──────────────────────────────────────────────────────
const gotLock = app.requestSingleInstanceLock()
if (!gotLock) { app.quit(); process.exit(0) }

// ── SHARED SECRET — lives only in process memory, never written to disk ───────
const TOKEN = randomUUID()

let win, tray, pythonProcess

// Renderer asks for the token via secure IPC — never via window globals
ipcMain.handle('get-token', () => TOKEN)

// ── PORT CHECK ────────────────────────────────────────────────────────────────
function isPortBusy(port) {
  return new Promise((resolve) => {
    const srv = net.createServer()
    srv.once('error', () => resolve(true))
    srv.once('listening', () => { srv.close(); resolve(false) })
    srv.listen(port, '127.0.0.1')
  })
}

// ── OLLAMA BACKEND ────────────────────────────────────────────────────────────
let ollamaProcess

async function startOllama() {
  const busy = await isPortBusy(11434)
  if (busy) {
    console.log('[ollama] already running on 11434 — skipping')
    return
  }
  const ollamaBin = '/Applications/Ollama.app/Contents/Resources/ollama'
  const fs = require('fs')
  if (!fs.existsSync(ollamaBin)) {
    console.log('[ollama] binary not found, skipping')
    return
  }
  ollamaProcess = spawn(ollamaBin, ['serve'], {
    env: { ...process.env, HOME: os.homedir() }
  })
  ollamaProcess.stdout.on('data', d => process.stdout.write('OLLAMA: ' + d))
  ollamaProcess.stderr.on('data', () => {})
  ollamaProcess.on('exit', code => console.log('[ollama] exit', code))
}

// ── PYTHON BACKEND ────────────────────────────────────────────────────────────
async function startPython() {
  const busy = await isPortBusy(7734)
  if (busy) {
    console.log('[python] already running on 7734 — skipping')
    return
  }
  const jarvisDir = path.join(os.homedir(), 'jarvis')
  pythonProcess = spawn('python3', [path.join(jarvisDir, 'main.py')], {
    cwd: jarvisDir,
    env: { ...process.env, JARVIS_TOKEN: TOKEN }
  })
  pythonProcess.stdout.on('data', d => process.stdout.write('PY: ' + d))
  pythonProcess.stderr.on('data', d => process.stderr.write('PY ERR: ' + d))
  pythonProcess.on('exit', code => console.log('[python] exit', code))
}

// ── WINDOW ────────────────────────────────────────────────────────────────────
function createWindow() {
  if (win && !win.isDestroyed()) { win.close(); win = null }

  win = new BrowserWindow({
    width: 1440,
    height: 900,
    frame: false,
    backgroundColor: '#020810',
    titleBarStyle: 'hiddenInset',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: false,  // needed: file:// → http://localhost cross-origin
      sandbox: false       // needed: preload uses Node crypto via IPC
    }
  })

  win.loadFile(path.join(__dirname, '../ui/hud.html'))
  win.on('closed', () => { win = null })
}

// ── TRAY ──────────────────────────────────────────────────────────────────────
function createTray() {
  if (tray && !tray.isDestroyed()) return
  tray = new Tray(nativeImage.createEmpty())
  tray.setToolTip('J.A.R.V.I.S.')
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: '⚡ Показать JARVIS', click: () => win ? win.show() : createWindow() },
    { label: '— Скрыть',          click: () => win && win.hide() },
    { type: 'separator' },
    { label: '⬛ Выключить',      click: () => app.quit() }
  ]))
}

// ── LIFECYCLE ─────────────────────────────────────────────────────────────────
app.on('second-instance', () => {
  if (win) { if (win.isMinimized()) win.restore(); win.focus() }
})

app.whenReady().then(() => {
  startOllama()
  startPython()
  createWindow()
  createTray()
})

app.on('before-quit', () => {
  if (pythonProcess) pythonProcess.kill()
  if (ollamaProcess) ollamaProcess.kill()
})
app.on('window-all-closed', () => app.quit())
