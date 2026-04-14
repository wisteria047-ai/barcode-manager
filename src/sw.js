// Service Worker — バーコード管理ツール v3.0
// Cache First 戦略: 全アセットをキャッシュし、オフラインで動作

const CACHE_NAME = 'barcode-manager-v3.0.4';

const ASSETS = [
  './',
  './index.html',
  './css/style.css',
  './js/platform.js',
  './js/i18n.js',
  './js/storage.js',
  './js/ui.js',
  './js/table.js',
  './js/importer.js',
  './js/printer.js',
  './js/scanner.js',
  './js/app.js',
  './vendor/html5-qrcode.min.js',
  './vendor/dexie.min.js',
  './vendor/xlsx.full.min.js',
  './vendor/JsBarcode.all.min.js',
  './vendor/qrcode.min.js',
  './vendor/jspdf.umd.min.js',
  './locales/ja.json',
  './locales/en.json',
  './manifest.json'
];

// Install: 全アセットをプリキャッシュ
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

// Activate: 旧キャッシュを削除
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

// Fetch: Cache First → ネットワークフォールバック
self.addEventListener('fetch', (event) => {
  // POST や非 GET リクエストはキャッシュしない
  if (event.request.method !== 'GET') return;

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((response) => {
        // 正常なレスポンスのみキャッシュに追加
        if (response.ok && response.type === 'basic') {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      });
    }).catch(() => {
      // オフラインでキャッシュにもない場合
      if (event.request.destination === 'document') {
        return caches.match('./index.html');
      }
    })
  );
});
