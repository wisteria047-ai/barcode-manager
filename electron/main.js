const { app, BrowserWindow, Menu, session } = require('electron');
const path = require('path');

const appRoot = path.join(__dirname, '..');

// CSP ヘッダーをすべてのレスポンスに付与
app.on('ready', () => {
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [
          "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; worker-src 'self';"
        ]
      }
    });
  });
});

// セキュリティ: レンダラーからのリモートコンテンツを防止
app.on('web-contents-created', (event, contents) => {
  contents.on('will-navigate', (event, url) => {
    // 別窓（ポップアウト）用のハッシュナビゲーションは許可
    if (url.startsWith('file://') && url.includes('#panel-')) return;
    event.preventDefault();
  });
  contents.setWindowOpenHandler(({ url }) => {
    // 別窓（ポップアウト）用: file:// + #panel-xxx のURLのみ許可
    if (url.startsWith('file://') && url.includes('#panel-')) {
      return {
        action: 'allow',
        overrideBrowserWindowOptions: {
          width: 900,
          height: 700,
          minWidth: 600,
          minHeight: 400,
          icon: path.join(appRoot, 'icons', 'icon-512.png'),
          autoHideMenuBar: true,
          webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            sandbox: true
          }
        }
      };
    }
    return { action: 'deny' };
  });
});

function createWindow() {
  const win = new BrowserWindow({
    width: 1200,
    height: 850,
    minWidth: 800,
    minHeight: 600,
    title: 'バーコード管理ツール',
    icon: path.join(appRoot, 'icons', 'icon-512.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true
    },
    autoHideMenuBar: true
  });

  // メニューバーを簡素化（印刷機能はアプリ内で提供）
  const menu = Menu.buildFromTemplate([
    {
      label: 'ファイル',
      submenu: [
        { label: '印刷', accelerator: 'CmdOrCtrl+P', click: () => win.webContents.print() },
        { type: 'separator' },
        { label: '終了', accelerator: 'Alt+F4', role: 'quit' }
      ]
    },
    {
      label: '表示',
      submenu: [
        { label: '拡大', accelerator: 'CmdOrCtrl+=', role: 'zoomIn' },
        { label: '縮小', accelerator: 'CmdOrCtrl+-', role: 'zoomOut' },
        { label: 'リセット', accelerator: 'CmdOrCtrl+0', role: 'resetZoom' },
        { type: 'separator' },
        { label: '全画面', accelerator: 'F11', role: 'togglefullscreen' }
      ]
    },
    {
      label: 'ヘルプ',
      submenu: [
        {
          label: 'バージョン情報',
          click: () => {
            const { dialog } = require('electron');
            dialog.showMessageBox(win, {
              type: 'info',
              title: 'バーコード管理ツール',
              message: 'バーコード管理ツール v2.0',
              detail: 'バーコード・QRコードの生成・印刷・貸出管理ができるデスクトップアプリです。\n\n© 2025 All rights reserved.'
            });
          }
        }
      ]
    }
  ]);
  Menu.setApplicationMenu(menu);

  win.loadFile(path.join(appRoot, 'index.html'));
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
