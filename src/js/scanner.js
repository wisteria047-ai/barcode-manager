// scanner — スキャンパネル・即時/一括モード・貸出/返却・カメラスキャン
const Scanner = (() => {
  let mode = 'immediate'; // 'immediate' | 'batch'
  let batchList = [];
  let operators = [];
  let scanCount = 0;
  let cameraScanner = null;
  let isCameraActive = false;

  async function init() {
    operators = await Storage.getSetting('operators', []);
    bindEvents();
    initCameraButton();
  }

  function bindEvents() {
    // モード切替
    document.querySelectorAll('.scan-mode-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.scan-mode-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        mode = btn.dataset.mode;
        updateBatchUI();
      });
    });

    // スキャン入力（Enter で実行）
    document.getElementById('scan-input')?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const value = e.target.value.trim();
        if (value) {
          handleScan(value);
          e.target.value = '';
        }
      }
    });

    // 一括適用ボタン
    document.getElementById('btn-batch-apply')?.addEventListener('click', applyBatch);

    // ツールバーのステータス変更ボタン
    document.getElementById('btn-status-returned')?.addEventListener('click', () => {
      changeSelectedStatus('returned');
    });
    document.getElementById('btn-status-collected')?.addEventListener('click', () => {
      changeSelectedStatus('collected');
    });

    // 一括削除
    document.getElementById('btn-delete-selected')?.addEventListener('click', deleteSelectedRows);

    // カメラスキャン開始/停止
    document.getElementById('btn-camera-scan')?.addEventListener('click', toggleCameraScan);
    document.getElementById('btn-camera-scan-stop')?.addEventListener('click', stopCameraScan);
  }

  // --- カメラスキャン ---
  function initCameraButton() {
    const btn = document.getElementById('btn-camera-scan');
    if (!btn) return;

    // カメラAPIがなければボタンを非表示
    if (!Platform.hasCameraSupport()) {
      btn.style.display = 'none';
      return;
    }
  }

  async function toggleCameraScan() {
    if (isCameraActive) {
      await stopCameraScan();
      return;
    }
    await startCameraScan();
  }

  async function startCameraScan() {
    if (typeof Html5Qrcode === 'undefined') {
      showToast(I18n.t('scanner.cameraNotAvailable'), 'error');
      return;
    }

    const modal = document.getElementById('camera-scan-modal');
    if (!modal) return;

    modal.classList.add('visible');
    isCameraActive = true;
    document.getElementById('btn-camera-scan')?.classList.add('active');

    try {
      cameraScanner = new Html5Qrcode('camera-viewfinder');

      await cameraScanner.start(
        { facingMode: 'environment' },
        {
          fps: 10,
          qrbox: { width: 280, height: 160 },
          aspectRatio: 1.0,
        },
        onCameraScanSuccess,
        () => {} // ignore scan failures (no match yet)
      );
    } catch (err) {
      isCameraActive = false;
      modal.classList.remove('visible');
      document.getElementById('btn-camera-scan')?.classList.remove('active');

      if (err.toString().includes('NotAllowedError') || err.toString().includes('Permission')) {
        showToast(I18n.t('scanner.cameraPermissionDenied'), 'error');
      } else {
        showToast(I18n.t('scanner.cameraNotAvailable'), 'error');
      }
    }
  }

  function onCameraScanSuccess(decodedText) {
    if (!decodedText || !isCameraActive) return;

    // 読取成功 → 振動フィードバック（モバイル）
    if (navigator.vibrate) {
      navigator.vibrate(100);
    }

    showToast(I18n.t('scanner.cameraScanSuccess'), 'success', 1500);

    // 既存のスキャン処理に流し込む
    handleScan(decodedText);

    // 連続スキャンのため一時停止してから再開
    if (cameraScanner) {
      cameraScanner.pause(true);
      setTimeout(() => {
        if (isCameraActive && cameraScanner) {
          try { cameraScanner.resume(); } catch { /* ignore */ }
        }
      }, 1500);
    }
  }

  async function stopCameraScan() {
    isCameraActive = false;
    document.getElementById('btn-camera-scan')?.classList.remove('active');

    if (cameraScanner) {
      try {
        await cameraScanner.stop();
      } catch { /* ignore */ }
      cameraScanner = null;
    }

    // viewfinder をクリア
    const viewfinder = document.getElementById('camera-viewfinder');
    if (viewfinder) viewfinder.innerHTML = '';

    const modal = document.getElementById('camera-scan-modal');
    if (modal) modal.classList.remove('visible');
  }

  // --- スキャン処理 ---
  async function handleScan(barcodeValue) {
    scanCount++;
    updateScanCount();

    // バーコードプレビュー更新
    updateBarcodePreview(barcodeValue);

    // データベースから品目検索
    const items = Table.getItems();
    const barcodeCol = await getBarcodeColumn();
    const matches = items.filter((item) => {
      return Object.values(item).some((val) =>
        val != null && String(val).trim() === barcodeValue
      );
    });

    if (matches.length === 0) {
      showToast(I18n.t('lending.itemNotFound'), 'error');
      addHistoryEntry('scan', barcodeValue, null, 'not_found');
      return;
    }

    if (matches.length > 1) {
      showItemSelector(matches, barcodeValue);
      return;
    }

    const item = matches[0];

    if (mode === 'immediate') {
      await handleImmediateScan(item);
    } else {
      addToBatch(item, barcodeValue);
    }
  }

  async function getBarcodeColumn() {
    const cols = Table.getColumns();
    return cols.length > 0 ? cols[0].key : null;
  }

  // --- 即時反映モード ---
  async function handleImmediateScan(item) {
    const currentStatus = item._status || 'available';
    const itemName = getItemDisplayName(item);

    if (currentStatus === 'available') {
      // 貸出フォームを表示
      showLendForm(item);
    } else if (currentStatus === 'lent') {
      // 返却処理
      await returnItem(item);
    } else {
      // その他ステータス → available にトグル
      await Storage.updateItem(item.id, { _status: 'available', _lentTo: null, _dueDate: null });
      await Table.loadData();
      showToast(I18n.t('lending.scanToggled', { item: itemName }), 'success');
      addHistoryEntry('toggle', itemName, null, 'available');
    }
  }

  // --- 貸出フォーム ---
  function showLendForm(item) {
    const itemName = getItemDisplayName(item);
    const modal = document.getElementById('confirm-modal');
    const title = document.getElementById('confirm-title');
    const body = document.getElementById('confirm-body');
    const okBtn = document.getElementById('confirm-ok');
    const cancelBtn = document.getElementById('confirm-cancel');

    title.textContent = I18n.t('lending.lendForm');

    // フォームHTML
    body.innerHTML = `
      <p style="margin-bottom:12px;color:var(--color-text);">${itemName}</p>
      <div style="margin-bottom:12px;">
        <label style="display:block;font-size:12px;font-weight:600;color:var(--color-text-secondary);margin-bottom:4px;">${I18n.t('lending.borrower')}</label>
        <input type="text" id="lend-borrower" list="borrower-list" placeholder="${I18n.t('lending.borrowerPlaceholder')}" style="width:100%;height:36px;padding:0 10px;border:1px solid var(--color-border);border-radius:var(--radius-md);background:var(--color-bg);color:var(--color-text);">
        <datalist id="borrower-list">
          ${operators.map((op) => `<option value="${op}">`).join('')}
        </datalist>
      </div>
      <div>
        <label style="display:block;font-size:12px;font-weight:600;color:var(--color-text-secondary);margin-bottom:4px;">${I18n.t('lending.dueDate')}</label>
        <input type="date" id="lend-due-date" style="width:100%;height:36px;padding:0 10px;border:1px solid var(--color-border);border-radius:var(--radius-md);background:var(--color-bg);color:var(--color-text);">
      </div>
    `;

    okBtn.textContent = I18n.t('lending.lendBtn');
    okBtn.className = 'btn btn--primary';
    okBtn.style.background = '';
    cancelBtn.textContent = I18n.t('confirm.cancel');
    modal.classList.add('visible');

    // フォーカス
    setTimeout(() => document.getElementById('lend-borrower')?.focus(), 100);

    const cleanup = () => {
      modal.classList.remove('visible');
      okBtn.replaceWith(okBtn.cloneNode(true));
      cancelBtn.replaceWith(cancelBtn.cloneNode(true));
    };

    document.getElementById('confirm-ok').addEventListener('click', async () => {
      const borrower = document.getElementById('lend-borrower')?.value.trim();
      const dueDate = document.getElementById('lend-due-date')?.value;

      if (!borrower) {
        document.getElementById('lend-borrower')?.focus();
        return;
      }

      cleanup();
      await lendItem(item, borrower, dueDate);
    }, { once: true });

    document.getElementById('confirm-cancel').addEventListener('click', cleanup, { once: true });
  }

  async function lendItem(item, borrower, dueDate) {
    const now = new Date().toISOString();
    await Storage.updateItem(item.id, {
      _status: 'lent',
      _lentTo: borrower,
      _lentAt: now,
      _dueDate: dueDate || null,
    });

    // 操作者を自動登録
    if (borrower && !operators.includes(borrower)) {
      operators.push(borrower);
      await Storage.setSetting('operators', operators);
    }

    await Table.loadData();
    const itemName = getItemDisplayName(item);
    showToast(I18n.t('lending.lentSuccess', { item: itemName, name: borrower }), 'success');
    addHistoryEntry('lend', itemName, borrower);
  }

  // --- 返却処理 ---
  async function returnItem(item) {
    const now = new Date().toISOString();
    const borrower = item._lentTo || '';
    await Storage.updateItem(item.id, {
      _status: 'available',
      _lentTo: null,
      _dueDate: null,
      _returnedAt: now,
    });

    await Table.loadData();
    const itemName = getItemDisplayName(item);
    showToast(I18n.t('lending.returnSuccess', { item: itemName }), 'success');
    addHistoryEntry('return', itemName, borrower);
  }

  // --- 一括モード ---
  function addToBatch(item, barcodeValue) {
    const itemName = getItemDisplayName(item);
    batchList.push({ item, barcodeValue, itemName });
    updateBatchUI();
    showToast(`${itemName}`, 'info', 1500);
  }

  function updateBatchUI() {
    const countEl = document.getElementById('scan-count');
    if (countEl) {
      if (mode === 'batch' && batchList.length > 0) {
        countEl.textContent = I18n.t('scanner.scannedCount', { count: batchList.length });
      } else {
        countEl.textContent = '';
      }
    }

    // 一括適用ボタンの表示制御
    let applyBtn = document.getElementById('btn-batch-apply');
    if (mode === 'batch' && batchList.length > 0) {
      if (!applyBtn) {
        applyBtn = document.createElement('button');
        applyBtn.id = 'btn-batch-apply';
        applyBtn.className = 'btn btn--primary';
        applyBtn.style.cssText = 'width:100%;margin-top:8px;';
        applyBtn.textContent = `${I18n.t('scanner.apply')} (${batchList.length})`;
        applyBtn.addEventListener('click', applyBatch);
        document.getElementById('scan-count')?.parentElement?.appendChild(applyBtn);
      } else {
        applyBtn.textContent = `${I18n.t('scanner.apply')} (${batchList.length})`;
        applyBtn.style.display = '';
      }
    } else if (applyBtn) {
      applyBtn.style.display = 'none';
    }
  }

  async function applyBatch() {
    for (const entry of batchList) {
      await handleImmediateScan(entry.item);
    }
    batchList = [];
    updateBatchUI();
  }

  // --- ステータス変更（選択行） ---
  async function changeSelectedStatus(status) {
    const selectedIds = Table.getSelectedIds();
    if (selectedIds.length === 0) return;

    for (const id of selectedIds) {
      await Storage.updateItem(id, { _status: status });
    }

    await Table.loadData();
    showToast(I18n.t('lending.statusChanged', { count: selectedIds.length, status: I18n.t('filter.status' + capitalize(status)) }), 'success');
  }

  async function deleteSelectedRows() {
    const selectedIds = Table.getSelectedIds();
    if (selectedIds.length === 0) return;

    const items = [];
    for (const id of selectedIds) {
      const item = await Storage.getItemById(id);
      if (item) items.push(item);
      await Storage.deleteItem(id);
    }

    await Table.loadData();
    showUndo(`${items.length}${I18n.t('undo.deleted')}`, async () => {
      for (const item of items) {
        await Storage.addItem(item);
      }
      await Table.loadData();
    });
  }

  // --- バーコードプレビュー ---
  function updateBarcodePreview(value) {
    const previewArea = document.getElementById('barcode-preview');
    if (!previewArea || !value) return;

    previewArea.innerHTML = '<svg id="sidebar-barcode"></svg>';
    try {
      JsBarcode('#sidebar-barcode', value, {
        format: 'CODE128',
        width: 2,
        height: 60,
        displayValue: true,
        fontSize: 14,
        margin: 4,
      });
      document.getElementById('btn-barcode-print').disabled = false;
      document.getElementById('btn-barcode-save').disabled = false;
    } catch {
      previewArea.innerHTML = '<p style="color:var(--color-danger);font-size:12px;">—</p>';
    }
  }

  // --- 操作履歴 ---
  async function addHistoryEntry(action, itemName, operator, detail) {
    const now = new Date();
    const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;

    const entry = { action, itemName, operator, detail, time: timeStr };
    await Storage.addHistory(entry);

    // UIに追加
    const list = document.getElementById('history-list');
    if (!list) return;

    // 初回のプレースホルダーを削除
    if (list.children.length === 1 && list.firstElementChild.textContent === '—') {
      list.innerHTML = '';
    }

    const li = document.createElement('li');
    const actionLabel = action === 'lend' ? I18n.t('lending.lend')
      : action === 'return' ? I18n.t('lending.return')
      : action === 'toggle' ? '⟳'
      : '🔍';
    li.textContent = `${timeStr} ${actionLabel} ${itemName}${operator ? ` → ${operator}` : ''}`;

    list.insertBefore(li, list.firstChild);

    // 最大20件
    while (list.children.length > 20) {
      list.removeChild(list.lastChild);
    }
  }

  function updateScanCount() {
    // scanCountの更新（即時モード用）
  }

  // --- 操作者管理 ---
  function getOperators() {
    return operators;
  }

  async function addOperator(name) {
    if (!name || operators.includes(name)) return;
    operators.push(name);
    await Storage.setSetting('operators', operators);
    showToast(I18n.t('operator.added', { name }), 'success');
  }

  async function removeOperator(name) {
    operators = operators.filter((op) => op !== name);
    await Storage.setSetting('operators', operators);
    showToast(I18n.t('operator.deleted', { name }), 'success');
  }

  function showOperatorManager() {
    const modal = document.getElementById('confirm-modal');
    const title = document.getElementById('confirm-title');
    const body = document.getElementById('confirm-body');
    const okBtn = document.getElementById('confirm-ok');
    const cancelBtn = document.getElementById('confirm-cancel');

    title.textContent = I18n.t('operator.title');

    const renderList = () => {
      const listHtml = operators.length === 0
        ? `<p style="color:var(--color-text-muted);font-size:13px;">${I18n.t('operator.noOperators')}</p>`
        : operators.map((op) =>
          `<div style="display:flex;align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--color-border);">
            <span>${op}</span>
            <button class="action-btn action-btn--delete" data-op-delete="${op}">${I18n.t('operator.deleteBtn')}</button>
          </div>`
        ).join('');

      body.innerHTML = `
        <div style="margin-bottom:12px;">
          <div style="display:flex;gap:8px;">
            <input type="text" id="new-operator-name" placeholder="${I18n.t('operator.name')}" style="flex:1;height:32px;padding:0 10px;border:1px solid var(--color-border);border-radius:var(--radius-md);background:var(--color-bg);color:var(--color-text);">
            <button class="btn btn--primary btn--sm" id="btn-add-operator">${I18n.t('operator.addBtn')}</button>
          </div>
        </div>
        <div id="operator-list">${listHtml}</div>
      `;

      // 追加ボタン
      document.getElementById('btn-add-operator')?.addEventListener('click', async () => {
        const input = document.getElementById('new-operator-name');
        const name = input?.value.trim();
        if (name) {
          await addOperator(name);
          input.value = '';
          renderList();
        }
      });

      // 削除ボタン
      document.querySelectorAll('[data-op-delete]').forEach((btn) => {
        btn.addEventListener('click', async () => {
          await removeOperator(btn.dataset.opDelete);
          renderList();
        });
      });
    };

    renderList();
    okBtn.style.display = 'none';
    cancelBtn.textContent = I18n.t('confirm.cancel');
    modal.classList.add('visible');

    const cleanup = () => {
      modal.classList.remove('visible');
      okBtn.style.display = '';
      cancelBtn.replaceWith(cancelBtn.cloneNode(true));
    };

    document.getElementById('confirm-cancel').addEventListener('click', cleanup, { once: true });
  }

  // --- 複数件選択ダイアログ ---
  function showItemSelector(matches, barcodeValue) {
    const modal = document.getElementById('confirm-modal');
    const title = document.getElementById('confirm-title');
    const body = document.getElementById('confirm-body');
    const okBtn = document.getElementById('confirm-ok');
    const cancelBtn = document.getElementById('confirm-cancel');

    title.textContent = I18n.t('scan.selectItem');

    const cols = Table.getColumns();
    const displayCols = cols.slice(0, 3);

    let listHtml = matches.map((item, i) => {
      const details = displayCols.map((c) => item[c.key] || '').join(' / ');
      const status = item._status || 'available';
      const statusLabel = I18n.t(`lending.status${capitalize(status)}`) || status;
      return `<label style="display:flex;align-items:center;gap:8px;padding:8px;border:1px solid var(--color-border);border-radius:var(--radius-md);margin-bottom:4px;cursor:pointer;">
        <input type="radio" name="item-select" value="${i}" ${i === 0 ? 'checked' : ''}>
        <div style="flex:1;min-width:0;">
          <div style="font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${UI.escapeHtml(details)}</div>
          <div style="font-size:12px;color:var(--color-text-muted);">${statusLabel}</div>
        </div>
      </label>`;
    }).join('');

    body.innerHTML = `
      <p style="margin-bottom:12px;font-size:13px;color:var(--color-text-secondary);">${I18n.t('scan.selectItemDescription', { count: matches.length })}</p>
      <div>${listHtml}</div>
    `;

    okBtn.textContent = I18n.t('table.saveBtn');
    okBtn.className = 'btn btn--primary';
    okBtn.style.display = '';
    cancelBtn.textContent = I18n.t('confirm.cancel');
    modal.classList.add('visible');

    const cleanup = () => {
      modal.classList.remove('visible');
      okBtn.replaceWith(okBtn.cloneNode(true));
      cancelBtn.replaceWith(cancelBtn.cloneNode(true));
    };

    document.getElementById('confirm-ok').addEventListener('click', async () => {
      const selected = body.querySelector('input[name="item-select"]:checked');
      const idx = selected ? parseInt(selected.value, 10) : 0;
      cleanup();
      const item = matches[idx];
      if (mode === 'immediate') {
        await handleImmediateScan(item);
      } else {
        addToBatch(item, barcodeValue);
      }
    }, { once: true });

    document.getElementById('confirm-cancel').addEventListener('click', cleanup, { once: true });
  }

  // --- ユーティリティ ---
  function getItemDisplayName(item) {
    const cols = Table.getColumns();
    // 品名列を探す（名前に「品名」「名」を含む列、なければ2番目の列）
    const nameCol = cols.find((c) => /品名|名前|name/i.test(c.key) || /品名|名前|name/i.test(c.name))
      || cols[1] || cols[0];
    return nameCol ? (item[nameCol.key] || '') : '';
  }

  function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  return {
    init,
    handleScan,
    showOperatorManager,
    getOperators,
    startCameraScan,
    stopCameraScan,
    isCameraScanning: () => isCameraActive,
  };
})();

if (typeof module !== 'undefined' && module.exports) {
  module.exports = Scanner;
}
