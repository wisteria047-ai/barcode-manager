// platform — プラットフォーム検出ユーティリティ
const Platform = (() => {
  const _global = typeof window !== 'undefined' ? window : globalThis;

  const isCapacitor = () => typeof _global.Capacitor !== 'undefined';
  const isElectron = () => typeof _global.electronAPI !== 'undefined';
  const isMobile = () => isCapacitor() || /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
  const isDesktop = () => isElectron() || (!isMobile());

  /** カメラAPI が利用可能か */
  const hasCameraSupport = () =>
    typeof navigator.mediaDevices !== 'undefined' &&
    typeof navigator.mediaDevices.getUserMedia === 'function';

  /** 現在のプラットフォーム名 */
  const name = () => {
    if (isElectron()) return 'electron';
    if (isCapacitor()) return 'capacitor';
    return 'web';
  };

  return { isCapacitor, isElectron, isMobile, isDesktop, hasCameraSupport, name };
})();

if (typeof module !== 'undefined' && module.exports) {
  module.exports = Platform;
}
