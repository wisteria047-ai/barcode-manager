import { describe, it, expect, beforeEach } from 'vitest';
import { readFileSync } from 'fs';
import { resolve } from 'path';

const srcDir = resolve(__dirname, '../src');

describe('PWA manifest.json', () => {
  let manifest;

  beforeEach(() => {
    const raw = readFileSync(resolve(srcDir, 'manifest.json'), 'utf-8');
    manifest = JSON.parse(raw);
  });

  it('should have required PWA fields', () => {
    expect(manifest.name).toBeTruthy();
    expect(manifest.short_name).toBeTruthy();
    expect(manifest.start_url).toBeTruthy();
    expect(manifest.display).toBe('standalone');
    expect(manifest.theme_color).toMatch(/^#[0-9a-fA-F]{6}$/);
    expect(manifest.background_color).toMatch(/^#[0-9a-fA-F]{6}$/);
  });

  it('should have icons with required sizes', () => {
    expect(manifest.icons).toBeInstanceOf(Array);
    const sizes = manifest.icons.map((i) => i.sizes);
    expect(sizes).toContain('192x192');
    expect(sizes).toContain('512x512');
  });

  it('should have at least one maskable icon', () => {
    const maskable = manifest.icons.filter((i) => i.purpose === 'maskable');
    expect(maskable.length).toBeGreaterThanOrEqual(1);
  });

  it('should reference existing icon files', () => {
    for (const icon of manifest.icons) {
      const iconPath = resolve(srcDir, icon.src);
      expect(() => readFileSync(iconPath)).not.toThrow();
    }
  });
});

describe('Service Worker sw.js', () => {
  let swSource;

  beforeEach(() => {
    swSource = readFileSync(resolve(srcDir, 'sw.js'), 'utf-8');
  });

  it('should define a cache name', () => {
    expect(swSource).toMatch(/CACHE_NAME\s*=\s*'/);
  });

  it('should list all app assets for precaching', () => {
    const requiredAssets = [
      'index.html',
      'css/style.css',
      'js/app.js',
      'js/i18n.js',
      'js/storage.js',
      'js/table.js',
      'js/scanner.js',
      'js/printer.js',
      'js/importer.js',
      'js/ui.js',
      'js/platform.js',
      'vendor/dexie.min.js',
      'vendor/xlsx.full.min.js',
      'vendor/JsBarcode.all.min.js',
      'vendor/qrcode.min.js',
      'vendor/jspdf.umd.min.js',
      'vendor/html5-qrcode.min.js',
      'locales/ja.json',
      'locales/en.json'
    ];
    for (const asset of requiredAssets) {
      expect(swSource).toContain(asset);
    }
  });

  it('should handle install event', () => {
    expect(swSource).toContain("addEventListener('install'");
  });

  it('should handle activate event with old cache cleanup', () => {
    expect(swSource).toContain("addEventListener('activate'");
    expect(swSource).toContain('caches.delete');
  });

  it('should handle fetch event with cache-first strategy', () => {
    expect(swSource).toContain("addEventListener('fetch'");
    expect(swSource).toContain('caches.match');
  });

  it('should skip non-GET requests', () => {
    expect(swSource).toContain("request.method !== 'GET'");
  });

  it('should call skipWaiting on install', () => {
    expect(swSource).toContain('self.skipWaiting()');
  });

  it('should call clients.claim on activate', () => {
    expect(swSource).toContain('self.clients.claim()');
  });
});

describe('index.html PWA integration', () => {
  let html;

  beforeEach(() => {
    html = readFileSync(resolve(srcDir, 'index.html'), 'utf-8');
  });

  it('should link to manifest.json', () => {
    expect(html).toContain('rel="manifest"');
    expect(html).toContain('manifest.json');
  });

  it('should have theme-color meta tag', () => {
    expect(html).toContain('name="theme-color"');
  });

  it('should have apple-mobile-web-app meta tags', () => {
    expect(html).toContain('apple-mobile-web-app-capable');
    expect(html).toContain('apple-touch-icon');
  });

  it('should register service worker', () => {
    expect(html).toContain("serviceWorker.register('./sw.js')");
  });

  it('should handle beforeinstallprompt', () => {
    expect(html).toContain('beforeinstallprompt');
  });

  it('should not reference any CDN URLs', () => {
    expect(html).not.toContain('unpkg.com');
    expect(html).not.toContain('cdn.jsdelivr.net');
    expect(html).not.toContain('cdnjs.cloudflare.com');
  });
});
