import { describe, it, expect } from 'vitest';
import { readFileSync, existsSync } from 'fs';
import { resolve } from 'path';

const root = resolve(__dirname, '..');
const srcDir = resolve(root, 'src');

describe('Store: electron-builder config', () => {
  let config;

  it('should have electron-builder.json', () => {
    const raw = readFileSync(resolve(root, 'electron-builder.json'), 'utf-8');
    config = JSON.parse(raw);
    expect(config.appId).toBe('com.barcode.manager');
  });

  it('should have Windows NSIS target', () => {
    const raw = readFileSync(resolve(root, 'electron-builder.json'), 'utf-8');
    config = JSON.parse(raw);
    expect(config.win.target).toBeInstanceOf(Array);
    expect(config.win.target[0].target).toBe('nsis');
  });
});

describe('Store: build scripts in package.json', () => {
  let pkg;

  it('should have build:electron script', () => {
    pkg = JSON.parse(readFileSync(resolve(root, 'package.json'), 'utf-8'));
    expect(pkg.scripts['build:electron']).toBeTruthy();
  });

  it('should have build:android script', () => {
    pkg = JSON.parse(readFileSync(resolve(root, 'package.json'), 'utf-8'));
    expect(pkg.scripts['build:android']).toBeTruthy();
  });
});

describe('Store: metadata files', () => {
  it('should have Japanese description', () => {
    expect(existsSync(resolve(root, 'store/description-ja.md'))).toBe(true);
  });

  it('should have English description', () => {
    expect(existsSync(resolve(root, 'store/description-en.md'))).toBe(true);
  });

  it('should have privacy policy', () => {
    expect(existsSync(resolve(root, 'store/privacy-policy.md'))).toBe(true);
  });
});

describe('Store: icons', () => {
  it('should have PWA icons (192 and 512)', () => {
    expect(existsSync(resolve(srcDir, 'assets/icons/icon-192.png'))).toBe(true);
    expect(existsSync(resolve(srcDir, 'assets/icons/icon-512.png'))).toBe(true);
  });

  it('should have maskable PWA icons', () => {
    expect(existsSync(resolve(srcDir, 'assets/icons/icon-maskable-192.png'))).toBe(true);
    expect(existsSync(resolve(srcDir, 'assets/icons/icon-maskable-512.png'))).toBe(true);
  });

  it('should have Android icons for all densities', () => {
    const densities = ['mdpi', 'hdpi', 'xhdpi', 'xxhdpi', 'xxxhdpi'];
    const resDir = resolve(root, 'android/app/src/main/res');
    for (const d of densities) {
      expect(existsSync(resolve(resDir, `mipmap-${d}/ic_launcher.png`))).toBe(true);
    }
  });
});
