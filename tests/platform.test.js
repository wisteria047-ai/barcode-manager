import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

/**
 * Platform 検出テスト
 * platform.js は IIFE でグローバルに公開される設計のため、
 * テスト用にコア関数を再実装してテストする（i18n.test.js と同方式）
 */
describe('Platform detection', () => {
  const originalUA = navigator.userAgent;

  // platform.js のコアロジックを再実装
  function createPlatform(env = {}) {
    const _global = env.globals || {};

    const isCapacitor = () => typeof _global.Capacitor !== 'undefined';
    const isElectron = () => typeof _global.electronAPI !== 'undefined';
    const isMobile = () =>
      isCapacitor() || /Android|iPhone|iPad|iPod/i.test(env.userAgent || '');
    const isDesktop = () => isElectron() || !isMobile();

    const hasCameraSupport = () =>
      env.mediaDevices != null &&
      typeof env.mediaDevices.getUserMedia === 'function';

    const name = () => {
      if (isElectron()) return 'electron';
      if (isCapacitor()) return 'capacitor';
      return 'web';
    };

    return { isCapacitor, isElectron, isMobile, isDesktop, hasCameraSupport, name };
  }

  it('should detect Electron environment', () => {
    const P = createPlatform({ globals: { electronAPI: {} } });
    expect(P.isElectron()).toBe(true);
    expect(P.name()).toBe('electron');
    expect(P.isDesktop()).toBe(true);
  });

  it('should detect Capacitor environment', () => {
    const P = createPlatform({ globals: { Capacitor: { isNativePlatform: () => true } } });
    expect(P.isCapacitor()).toBe(true);
    expect(P.name()).toBe('capacitor');
    expect(P.isMobile()).toBe(true);
  });

  it('should detect web (browser) environment', () => {
    const P = createPlatform({ globals: {} });
    expect(P.isElectron()).toBe(false);
    expect(P.isCapacitor()).toBe(false);
    expect(P.name()).toBe('web');
  });

  it('should detect mobile via user agent when not Capacitor', () => {
    const P = createPlatform({
      userAgent: 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/120',
    });
    expect(P.isMobile()).toBe(true);
    expect(P.isDesktop()).toBe(false);
  });

  it('should detect desktop via user agent', () => {
    const P = createPlatform({
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    });
    expect(P.isMobile()).toBe(false);
    expect(P.isDesktop()).toBe(true);
  });

  it('should detect iPhone as mobile', () => {
    const P = createPlatform({
      userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)',
    });
    expect(P.isMobile()).toBe(true);
  });

  it('should detect iPad as mobile', () => {
    const P = createPlatform({
      userAgent: 'Mozilla/5.0 (iPad; CPU OS 17_0)',
    });
    expect(P.isMobile()).toBe(true);
  });

  it('should report camera support when mediaDevices available', () => {
    const P = createPlatform({ mediaDevices: { getUserMedia: vi.fn() } });
    expect(P.hasCameraSupport()).toBe(true);
  });

  it('should report no camera support when mediaDevices missing', () => {
    const P = createPlatform({ mediaDevices: undefined });
    expect(P.hasCameraSupport()).toBe(false);
  });

  it('should report no camera support when getUserMedia missing', () => {
    const P = createPlatform({ mediaDevices: {} });
    expect(P.hasCameraSupport()).toBe(false);
  });

  it('Capacitor overrides user agent for mobile detection', () => {
    const P = createPlatform({
      globals: { Capacitor: {} },
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)', // desktop UA
    });
    expect(P.isMobile()).toBe(true); // Capacitor = mobile regardless of UA
  });

  it('Electron is prioritized over Capacitor in name()', () => {
    const P = createPlatform({
      globals: { electronAPI: {}, Capacitor: {} },
    });
    expect(P.name()).toBe('electron');
  });
});
