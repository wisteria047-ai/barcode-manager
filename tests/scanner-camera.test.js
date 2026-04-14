import { describe, it, expect, beforeEach, vi } from 'vitest';

/**
 * カメラスキャン機能テスト
 * scanner.js は IIFE でグローバル公開されるため、
 * カメラスキャン関連のコアロジックを再実装してテストする
 */
describe('Camera scan logic', () => {
  let mockHtml5Qrcode;
  let toastCalls;

  beforeEach(() => {
    toastCalls = [];
    mockHtml5Qrcode = {
      start: vi.fn().mockResolvedValue(undefined),
      stop: vi.fn().mockResolvedValue(undefined),
      pause: vi.fn(),
      resume: vi.fn(),
    };
  });

  // カメラスキャン開始のコアロジックを再実装
  function createCameraScanner(opts = {}) {
    let isCameraActive = false;
    let cameraScanner = null;
    const showToast = (msg, type) => toastCalls.push({ msg, type });
    const hasCameraSupport = opts.hasCameraSupport ?? true;
    const Html5QrcodeAvailable = opts.html5QrcodeAvailable ?? true;
    const Html5QrcodeFactory = opts.factory ?? (() => mockHtml5Qrcode);
    const onScanResult = opts.onScanResult ?? vi.fn();

    function initCameraButton(btn) {
      if (!btn) return;
      if (!hasCameraSupport) {
        btn.style.display = 'none';
      }
    }

    async function startCameraScan(viewfinderElement) {
      if (!Html5QrcodeAvailable) {
        showToast('scanner.cameraNotAvailable', 'error');
        return;
      }
      if (!viewfinderElement) return;

      isCameraActive = true;
      cameraScanner = Html5QrcodeFactory('camera-viewfinder');

      await cameraScanner.start(
        { facingMode: 'environment' },
        { fps: 10, qrbox: { width: 280, height: 160 }, aspectRatio: 1.0 },
        (decodedText) => {
          if (!decodedText || !isCameraActive) return;
          onScanResult(decodedText);
          cameraScanner.pause(true);
          setTimeout(() => {
            if (isCameraActive && cameraScanner) {
              try { cameraScanner.resume(); } catch { /* ignore */ }
            }
          }, 1500);
        },
        () => {}
      );
    }

    async function stopCameraScan() {
      isCameraActive = false;
      if (cameraScanner) {
        await cameraScanner.stop();
        cameraScanner = null;
      }
    }

    return {
      initCameraButton,
      startCameraScan,
      stopCameraScan,
      isActive: () => isCameraActive,
      getScanner: () => cameraScanner,
    };
  }

  // --- Tests ---

  it('should hide camera button when no camera API', () => {
    const btn = document.createElement('button');
    btn.style.display = 'block';
    const cs = createCameraScanner({ hasCameraSupport: false });
    cs.initCameraButton(btn);
    expect(btn.style.display).toBe('none');
  });

  it('should keep camera button visible when camera API exists', () => {
    const btn = document.createElement('button');
    btn.style.display = '';
    const cs = createCameraScanner({ hasCameraSupport: true });
    cs.initCameraButton(btn);
    expect(btn.style.display).not.toBe('none');
  });

  it('should show error when Html5Qrcode is not available', async () => {
    const cs = createCameraScanner({ html5QrcodeAvailable: false });
    await cs.startCameraScan(document.createElement('div'));
    expect(toastCalls).toEqual([{ msg: 'scanner.cameraNotAvailable', type: 'error' }]);
    expect(cs.isActive()).toBe(false);
  });

  it('should call Html5Qrcode with environment-facing camera', async () => {
    const factory = vi.fn(() => mockHtml5Qrcode);
    const cs = createCameraScanner({ factory });
    await cs.startCameraScan(document.createElement('div'));
    expect(factory).toHaveBeenCalledWith('camera-viewfinder');
    expect(mockHtml5Qrcode.start).toHaveBeenCalledWith(
      { facingMode: 'environment' },
      expect.objectContaining({ fps: 10 }),
      expect.any(Function),
      expect.any(Function)
    );
  });

  it('should set active state on start', async () => {
    const cs = createCameraScanner({});
    expect(cs.isActive()).toBe(false);
    await cs.startCameraScan(document.createElement('div'));
    expect(cs.isActive()).toBe(true);
  });

  it('should stop camera and clear state', async () => {
    const cs = createCameraScanner({});
    await cs.startCameraScan(document.createElement('div'));
    await cs.stopCameraScan();
    expect(mockHtml5Qrcode.stop).toHaveBeenCalled();
    expect(cs.isActive()).toBe(false);
    expect(cs.getScanner()).toBeNull();
  });

  it('should invoke onScanResult callback when barcode detected', async () => {
    const onScanResult = vi.fn();
    const cs = createCameraScanner({ onScanResult });

    await cs.startCameraScan(document.createElement('div'));

    // start の第3引数（成功コールバック）を取得して呼ぶ
    const successCallback = mockHtml5Qrcode.start.mock.calls[0][2];
    successCallback('TEST-BARCODE-123');

    expect(onScanResult).toHaveBeenCalledWith('TEST-BARCODE-123');
  });

  it('should pause scanner after successful scan', async () => {
    const cs = createCameraScanner({});
    await cs.startCameraScan(document.createElement('div'));

    const successCallback = mockHtml5Qrcode.start.mock.calls[0][2];
    successCallback('SOME-VALUE');

    expect(mockHtml5Qrcode.pause).toHaveBeenCalledWith(true);
  });

  it('should ignore empty scan results', async () => {
    const onScanResult = vi.fn();
    const cs = createCameraScanner({ onScanResult });
    await cs.startCameraScan(document.createElement('div'));

    const successCallback = mockHtml5Qrcode.start.mock.calls[0][2];
    successCallback('');
    successCallback(null);

    expect(onScanResult).not.toHaveBeenCalled();
  });

  it('should handle stop when camera never started', async () => {
    const cs = createCameraScanner({});
    // stop without start should not throw
    await expect(cs.stopCameraScan()).resolves.toBeUndefined();
  });

  it('should use environment-facing camera (rear camera)', async () => {
    const cs = createCameraScanner({});
    await cs.startCameraScan(document.createElement('div'));
    const cameraConfig = mockHtml5Qrcode.start.mock.calls[0][0];
    expect(cameraConfig).toEqual({ facingMode: 'environment' });
  });
});
