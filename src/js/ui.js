// ui — 共通UIユーティリティ（トースト・Undo・確認ダイアログ・エスケープ）
const UI = (() => {
  // --- HTML エスケープ ---
  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // --- トースト通知 ---
  let lastToastMessage = '';
  let lastToastTime = 0;

  function showToast(message, type = 'info', duration) {
    // 重複排除（100ms以内の同一メッセージ）
    const now = Date.now();
    if (message === lastToastMessage && now - lastToastTime < 100) return;
    lastToastMessage = message;
    lastToastTime = now;

    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.textContent = message;
    toast.setAttribute('role', type === 'error' ? 'alert' : 'status');
    container.appendChild(toast);

    // 最大3件
    while (container.children.length > 3) {
      container.removeChild(container.firstChild);
    }

    requestAnimationFrame(() => toast.classList.add('visible'));

    const autoClose = type === 'error' ? null : (duration || (type === 'success' ? 3000 : 5000));
    if (autoClose) {
      setTimeout(() => removeToast(toast), autoClose);
    }
  }

  function removeToast(toast) {
    toast.classList.remove('visible');
    setTimeout(() => toast.remove(), 200);
  }

  // --- Undoバー ---
  let undoTimer = null;

  function showUndo(message, onUndo) {
    const bar = document.getElementById('undo-bar');
    const msgEl = document.getElementById('undo-message');
    const btnEl = document.getElementById('btn-undo');

    if (!bar) return;

    msgEl.textContent = message;
    btnEl.textContent = I18n.t('undo.restore');
    bar.classList.add('visible');

    if (undoTimer) clearTimeout(undoTimer);

    const cleanup = () => {
      bar.classList.remove('visible');
      btnEl.replaceWith(btnEl.cloneNode(true));
    };

    document.getElementById('btn-undo').addEventListener('click', () => {
      if (undoTimer) clearTimeout(undoTimer);
      cleanup();
      onUndo();
    }, { once: true });

    undoTimer = setTimeout(cleanup, 8000);
  }

  // --- 確認ダイアログ ---
  function showConfirm(title, body, okLabel, onOk) {
    const modal = document.getElementById('confirm-modal');
    document.getElementById('confirm-title').textContent = title;
    document.getElementById('confirm-body').textContent = body;
    const okBtn = document.getElementById('confirm-ok');
    okBtn.textContent = okLabel;
    okBtn.className = 'btn btn--primary';
    if (okLabel === I18n.t('column.deleteBtn')) {
      okBtn.style.background = 'var(--color-danger)';
    }
    document.getElementById('confirm-cancel').textContent = I18n.t('confirm.cancel');
    modal.classList.add('visible');

    const cleanup = () => {
      modal.classList.remove('visible');
      okBtn.replaceWith(okBtn.cloneNode(true));
      document.getElementById('confirm-cancel').replaceWith(
        document.getElementById('confirm-cancel').cloneNode(true)
      );
    };

    document.getElementById('confirm-ok').addEventListener('click', () => {
      cleanup();
      onOk();
    }, { once: true });

    document.getElementById('confirm-cancel').addEventListener('click', cleanup, { once: true });

    // ESCで閉じる + フォーカストラップ
    const onKey = (e) => {
      if (e.key === 'Escape') { cleanup(); document.removeEventListener('keydown', onKey); }
      if (e.key === 'Tab') trapFocus(e, modal);
    };
    document.addEventListener('keydown', onKey);

    // キャンセルボタンにフォーカス（破壊的操作の安全デフォルト）
    setTimeout(() => document.getElementById('confirm-cancel')?.focus(), 50);
  }

  // --- フォーカストラップ（モーダル内） ---
  function trapFocus(e, container) {
    const focusable = container.querySelectorAll(
      'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    if (focusable.length === 0) return;

    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  return { escapeHtml, showToast, showUndo, showConfirm, trapFocus };
})();

if (typeof module !== 'undefined' && module.exports) {
  module.exports = UI;
}
