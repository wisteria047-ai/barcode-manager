// printer — バーコード生成・ラベル印刷・PDF出力
const Printer = (() => {
  // 用紙プリセット定義 (mm)
  const PRESETS = {
    'a4-24': { cols: 3, rows: 8, labelW: 70, labelH: 37, marginTop: 11, marginLeft: 0, gapH: 0, gapV: 0 },
    'a4-21': { cols: 3, rows: 7, labelW: 70, labelH: 42.3, marginTop: 15, marginLeft: 0, gapH: 0, gapV: 0 },
    'a4-10': { cols: 2, rows: 5, labelW: 86, labelH: 50.8, marginTop: 21.2, marginLeft: 19, gapH: 0, gapV: 0 },
  };

  let printSettings = {
    barcodeCol: null,
    barcodeFormat: 'CODE128',
    showText: true,
    preset: 'a4-24',
    cols: 3, rows: 8,
    labelW: 70, labelH: 37,
    marginTop: 11, marginLeft: 0,
    gapH: 0, gapV: 0,
    startPos: 1,
    fontSize: 8,
    barcodeHeight: 15,
    columnDisplay: {}, // key -> 'barcode' | 'text' | 'labelText' | 'hidden'
  };

  let currentPrintPage = 1;
  let printItems = [];
  let savedPresets = [];

  function init() {
    bindEvents();
  }

  function bindEvents() {
    // ラベル印刷ボタン
    document.getElementById('btn-print')?.addEventListener('click', openPrintModal);
    document.getElementById('btn-close-print')?.addEventListener('click', closePrintModal);
    document.getElementById('print-modal')?.addEventListener('click', (e) => {
      if (e.target === e.currentTarget) closePrintModal();
    });

    // プリセット変更
    document.getElementById('print-preset')?.addEventListener('change', (e) => {
      const preset = PRESETS[e.target.value];
      if (preset) {
        applyPreset(preset);
      }
      updatePreview();
    });

    // 設定変更で即プレビュー更新
    const settingInputs = [
      'print-barcode-col', 'print-barcode-format', 'print-show-text',
      'print-cols', 'print-rows', 'print-label-w', 'print-label-h',
      'print-margin-top', 'print-margin-left', 'print-gap-h', 'print-gap-v',
      'print-start-pos', 'print-font-size', 'print-barcode-height',
    ];
    settingInputs.forEach((id) => {
      document.getElementById(id)?.addEventListener('change', () => {
        readSettings();
        updatePreview();
      });
      document.getElementById(id)?.addEventListener('input', () => {
        readSettings();
        updatePreview();
      });
    });

    // ページ送り
    document.getElementById('btn-prev-print-page')?.addEventListener('click', () => {
      if (currentPrintPage > 1) { currentPrintPage--; renderPreview(); }
    });
    document.getElementById('btn-next-print-page')?.addEventListener('click', () => {
      const totalPages = getTotalPrintPages();
      if (currentPrintPage < totalPages) { currentPrintPage++; renderPreview(); }
    });

    // PDF保存・直接印刷
    document.getElementById('btn-save-pdf')?.addEventListener('click', savePdf);
    document.getElementById('btn-direct-print')?.addEventListener('click', directPrint);

    // 一括操作ボタン
    document.querySelectorAll('[data-quick]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const mode = btn.dataset.quick;
        applyQuickAction(mode);
      });
    });

    // プリセット保存/読込
    document.getElementById('btn-save-preset')?.addEventListener('click', saveCurrentPreset);
    document.getElementById('print-saved-presets')?.addEventListener('change', loadSavedPreset);

    // 右パネルのバーコードプレビュー
    document.getElementById('scan-input')?.addEventListener('input', updateSidebarPreview);
  }

  // --- モーダル制御 ---
  async function openPrintModal() {
    const selectedIds = Table.getSelectedIds();
    const allItems = Table.getItems();

    if (allItems.length === 0) return;

    printItems = selectedIds.length > 0
      ? allItems.filter((item) => selectedIds.includes(item.id))
      : allItems;

    // 保存済み設定を復元
    const saved = await Storage.getSetting('printSettings', null);
    if (saved) Object.assign(printSettings, saved);

    // 保存済みプリセット読込
    savedPresets = await Storage.getSetting('printPresets', []);

    populateColumnSelectors();
    writeSettings();
    populateSavedPresets();
    updatePreview();

    document.getElementById('print-modal')?.classList.add('visible');
    I18n.translatePage();
  }

  function closePrintModal() {
    document.getElementById('print-modal')?.classList.remove('visible');
  }

  // --- 設定UI ↔ printSettings ---
  function populateColumnSelectors() {
    const columns = Table.getColumns().filter((c) => c.visible !== false);

    // バーコード列選択
    const barcodeColSelect = document.getElementById('print-barcode-col');
    if (barcodeColSelect) {
      barcodeColSelect.innerHTML = columns.map((c) =>
        `<option value="${c.key}" ${c.key === printSettings.barcodeCol ? 'selected' : ''}>${c.name}</option>`
      ).join('');
      if (!printSettings.barcodeCol && columns.length > 0) {
        printSettings.barcodeCol = columns[0].key;
      }
    }

    // 列表示設定のトグル
    const togglesContainer = document.getElementById('print-column-toggles');
    if (!togglesContainer) return;

    togglesContainer.innerHTML = '';
    columns.forEach((col) => {
      const mode = printSettings.columnDisplay[col.key] || 'text';
      const div = document.createElement('div');
      div.className = 'print-col-toggle';
      div.innerHTML = `
        <span class="print-col-name">${col.name}</span>
        <select data-col-key="${col.key}" class="print-col-mode">
          <option value="barcode" ${mode === 'barcode' ? 'selected' : ''}>${I18n.t('print.displayAsBarcode')}</option>
          <option value="text" ${mode === 'text' ? 'selected' : ''}>${I18n.t('print.displayAsText')}</option>
          <option value="labelText" ${mode === 'labelText' ? 'selected' : ''}>${I18n.t('print.displayAsLabelText')}</option>
          <option value="hidden" ${mode === 'hidden' ? 'selected' : ''}>${I18n.t('print.displayHidden')}</option>
        </select>
      `;
      togglesContainer.appendChild(div);

      div.querySelector('select').addEventListener('change', (e) => {
        printSettings.columnDisplay[col.key] = e.target.value;
        updatePreview();
      });
    });
  }

  function readSettings() {
    printSettings.barcodeCol = document.getElementById('print-barcode-col')?.value || null;
    printSettings.barcodeFormat = document.getElementById('print-barcode-format')?.value || 'CODE128';
    printSettings.showText = document.getElementById('print-show-text')?.checked ?? true;
    printSettings.preset = document.getElementById('print-preset')?.value || 'a4-24';
    printSettings.cols = parseInt(document.getElementById('print-cols')?.value, 10) || 3;
    printSettings.rows = parseInt(document.getElementById('print-rows')?.value, 10) || 8;
    printSettings.labelW = parseFloat(document.getElementById('print-label-w')?.value) || 70;
    printSettings.labelH = parseFloat(document.getElementById('print-label-h')?.value) || 37;
    printSettings.marginTop = parseFloat(document.getElementById('print-margin-top')?.value) || 0;
    printSettings.marginLeft = parseFloat(document.getElementById('print-margin-left')?.value) || 0;
    printSettings.gapH = parseFloat(document.getElementById('print-gap-h')?.value) || 0;
    printSettings.gapV = parseFloat(document.getElementById('print-gap-v')?.value) || 0;
    printSettings.startPos = parseInt(document.getElementById('print-start-pos')?.value, 10) || 1;
    printSettings.fontSize = document.getElementById('print-font-size')?.value || '8';
    printSettings.barcodeHeight = parseInt(document.getElementById('print-barcode-height')?.value, 10) || 15;

    // 自動保存
    Storage.setSetting('printSettings', printSettings);
  }

  function writeSettings() {
    const s = printSettings;
    setVal('print-barcode-col', s.barcodeCol);
    setVal('print-barcode-format', s.barcodeFormat);
    setChecked('print-show-text', s.showText);
    setVal('print-preset', s.preset);
    setVal('print-cols', s.cols);
    setVal('print-rows', s.rows);
    setVal('print-label-w', s.labelW);
    setVal('print-label-h', s.labelH);
    setVal('print-margin-top', s.marginTop);
    setVal('print-margin-left', s.marginLeft);
    setVal('print-gap-h', s.gapH);
    setVal('print-gap-v', s.gapV);
    setVal('print-start-pos', s.startPos);
    setVal('print-font-size', s.fontSize);
    setVal('print-barcode-height', s.barcodeHeight);
  }

  function setVal(id, val) {
    const el = document.getElementById(id);
    if (el && val != null) el.value = val;
  }
  function setChecked(id, val) {
    const el = document.getElementById(id);
    if (el) el.checked = !!val;
  }

  function applyPreset(preset) {
    printSettings.cols = preset.cols;
    printSettings.rows = preset.rows;
    printSettings.labelW = preset.labelW;
    printSettings.labelH = preset.labelH;
    printSettings.marginTop = preset.marginTop;
    printSettings.marginLeft = preset.marginLeft;
    printSettings.gapH = preset.gapH;
    printSettings.gapV = preset.gapV;
    writeSettings();
  }

  // --- 一括操作 ---
  function applyQuickAction(mode) {
    const columns = Table.getColumns().filter((c) => c.visible !== false);
    if (mode === 'default') {
      printSettings.columnDisplay = {};
      columns.forEach((col, i) => {
        printSettings.columnDisplay[col.key] = i === 0 ? 'barcode' : 'text';
      });
    } else {
      columns.forEach((col) => {
        printSettings.columnDisplay[col.key] = mode === 'barcode' ? 'barcode' : mode === 'text' ? 'text' : 'hidden';
      });
    }
    populateColumnSelectors();
    updatePreview();
  }

  // --- プリセット保存/読込 ---
  async function saveCurrentPreset() {
    const name = document.getElementById('print-preset-name')?.value.trim();
    if (!name) return;

    readSettings();
    savedPresets = savedPresets.filter((p) => p.name !== name);
    savedPresets.push({ name, settings: { ...printSettings } });
    await Storage.setSetting('printPresets', savedPresets);
    populateSavedPresets();
    showToast(`${name}`, 'success');
  }

  async function loadSavedPreset() {
    const name = document.getElementById('print-saved-presets')?.value;
    if (!name) return;
    const preset = savedPresets.find((p) => p.name === name);
    if (preset) {
      Object.assign(printSettings, preset.settings);
      writeSettings();
      populateColumnSelectors();
      updatePreview();
    }
  }

  function populateSavedPresets() {
    const select = document.getElementById('print-saved-presets');
    if (!select) return;
    select.innerHTML = '<option value="">—</option>' +
      savedPresets.map((p) => `<option value="${p.name}">${p.name}</option>`).join('');
  }

  // --- プレビュー ---
  function getTotalPrintPages() {
    const perPage = printSettings.cols * printSettings.rows;
    const offset = printSettings.startPos - 1;
    return Math.max(1, Math.ceil((printItems.length + offset) / perPage));
  }

  function updatePreview() {
    currentPrintPage = 1;
    renderPreview();
    updatePrintInfo();
  }

  function updatePrintInfo() {
    const perPage = printSettings.cols * printSettings.rows;
    const totalPages = getTotalPrintPages();
    const selectedIds = Table.getSelectedIds();

    const infoEl = document.getElementById('print-target-info');
    if (infoEl) {
      if (selectedIds.length > 0) {
        infoEl.textContent = I18n.t('print.targetInfo', {
          selected: printItems.length, pages: totalPages, perPage,
        });
      } else {
        infoEl.textContent = I18n.t('print.targetAll', {
          total: printItems.length, pages: totalPages, perPage,
        });
      }
    }

    const pageIndicator = document.getElementById('print-page-indicator');
    if (pageIndicator) pageIndicator.textContent = `${currentPrintPage}/${totalPages}`;

    document.getElementById('btn-prev-print-page').disabled = currentPrintPage <= 1;
    document.getElementById('btn-next-print-page').disabled = currentPrintPage >= totalPages;
  }

  function renderPreview() {
    const canvas = document.getElementById('print-preview-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    // A4サイズ（mm → px, 96dpi基準でスケール）
    const pageW_mm = 210;
    const pageH_mm = 297;
    const scale = 2.5; // mm → canvas px
    canvas.width = pageW_mm * scale;
    canvas.height = pageH_mm * scale;

    // 背景
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const s = printSettings;
    const perPage = s.cols * s.rows;
    const offset = s.startPos - 1;
    const pageStart = (currentPrintPage - 1) * perPage - offset;

    const columns = Table.getColumns().filter((c) => c.visible !== false);

    for (let row = 0; row < s.rows; row++) {
      for (let col = 0; col < s.cols; col++) {
        const slotIndex = row * s.cols + col;
        const itemIndex = pageStart + slotIndex;

        const x = (s.marginLeft + col * (s.labelW + s.gapH)) * scale;
        const y = (s.marginTop + row * (s.labelH + s.gapV)) * scale;
        const w = s.labelW * scale;
        const h = s.labelH * scale;

        // ラベル枠（薄いグレー）
        ctx.strokeStyle = '#e0e0e0';
        ctx.lineWidth = 0.5;
        ctx.strokeRect(x, y, w, h);

        if (itemIndex < 0 || itemIndex >= printItems.length) continue;

        const item = printItems[itemIndex];
        renderLabelContent(ctx, item, columns, x, y, w, h, scale);
      }
    }

    updatePrintInfo();
  }

  function renderLabelContent(ctx, item, columns, x, y, w, h, scale) {
    const s = printSettings;
    const padding = 2 * scale;
    let cursorY = y + padding;
    const maxY = y + h - padding;
    const fontSize = s.fontSize === 'auto' ? 8 : parseInt(s.fontSize, 10);
    const fontPx = fontSize * scale * 0.35;

    columns.forEach((col) => {
      if (cursorY >= maxY) return;
      const mode = s.columnDisplay[col.key] || 'text';
      if (mode === 'hidden') return;

      const val = item[col.key] ?? '';

      if (mode === 'barcode') {
        // バーコード描画
        const barcodeH = s.barcodeHeight * scale * 0.35;
        try {
          drawBarcodeOnCanvas(ctx, String(val), x + padding, cursorY, w - padding * 2, barcodeH, s);
          cursorY += barcodeH + 2;
        } catch (e) {
          ctx.fillStyle = '#cc0000';
          ctx.font = `${fontPx}px sans-serif`;
          ctx.fillText('Error', x + padding, cursorY + fontPx);
          cursorY += fontPx + 2;
        }
      } else if (mode === 'labelText') {
        ctx.fillStyle = '#666666';
        ctx.font = `${fontPx * 0.8}px sans-serif`;
        ctx.fillText(`${col.name}:`, x + padding, cursorY + fontPx * 0.8);
        ctx.fillStyle = '#000000';
        ctx.font = `${fontPx}px sans-serif`;
        const labelWidth = ctx.measureText(`${col.name}: `).width;
        ctx.fillText(String(val), x + padding + labelWidth, cursorY + fontPx * 0.8);
        cursorY += fontPx + 2;
      } else {
        // テキスト
        ctx.fillStyle = '#000000';
        ctx.font = `${fontPx}px sans-serif`;
        const lines = wrapText(ctx, String(val), w - padding * 2);
        const maxLines = 3;
        lines.slice(0, maxLines).forEach((line) => {
          if (cursorY + fontPx < maxY) {
            ctx.fillText(line, x + padding, cursorY + fontPx);
            cursorY += fontPx + 1;
          }
        });
      }
    });
  }

  function drawBarcodeOnCanvas(ctx, value, x, y, maxW, barcodeH, settings) {
    if (!value) return;

    if (settings.barcodeFormat === 'qr') {
      // QR: canvasで生成して転写
      const tempCanvas = document.createElement('canvas');
      QRCode.toCanvas(tempCanvas, value, { width: barcodeH, margin: 0 }, () => {});
      ctx.drawImage(tempCanvas, x + (maxW - barcodeH) / 2, y, barcodeH, barcodeH);
      return;
    }

    // JsBarcodeでSVG生成→canvas描画
    const svgNS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(svgNS, 'svg');
    try {
      JsBarcode(svg, value, {
        format: settings.barcodeFormat,
        width: 1.5,
        height: barcodeH * 0.7,
        displayValue: settings.showText,
        fontSize: 10,
        margin: 0,
      });
    } catch {
      return;
    }

    // SVG → Image → Canvas
    const svgData = new XMLSerializer().serializeToString(svg);
    const img = new Image();
    img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgData)));

    // 同期的にはできないので、簡易バーコード描画（線で）
    drawSimpleBarcode(ctx, value, x, y, maxW, barcodeH, settings);
  }

  // 簡易バーコード描画（Canvas直接）
  function drawSimpleBarcode(ctx, value, x, y, maxW, barcodeH, settings) {
    // Code128 簡易エンコード（視覚的なプレビュー用）
    ctx.fillStyle = '#000000';
    const charWidth = Math.min(2, maxW / (value.length * 11));
    let cx = x + (maxW - value.length * 11 * charWidth) / 2;

    for (let i = 0; i < value.length; i++) {
      const code = value.charCodeAt(i);
      // 各文字を縞模様で表現
      for (let b = 0; b < 11; b++) {
        const isFilled = ((code >> (b % 7)) & 1) === 1 || b % 3 === 0;
        if (isFilled) {
          ctx.fillRect(cx, y, charWidth, barcodeH * 0.7);
        }
        cx += charWidth;
      }
    }

    // バーコード下テキスト
    if (settings.showText) {
      ctx.fillStyle = '#000000';
      ctx.font = `${Math.max(8, barcodeH * 0.2)}px sans-serif`;
      ctx.textAlign = 'center';
      ctx.fillText(value, x + maxW / 2, y + barcodeH * 0.7 + barcodeH * 0.25);
      ctx.textAlign = 'start';
    }
  }

  function wrapText(ctx, text, maxWidth) {
    const words = text.split('');
    const lines = [];
    let line = '';
    for (const ch of words) {
      const test = line + ch;
      if (ctx.measureText(test).width > maxWidth && line) {
        lines.push(line);
        line = ch;
      } else {
        line = test;
      }
    }
    if (line) lines.push(line);
    return lines;
  }

  // --- PDF生成 ---
  async function savePdf() {
    showToast(I18n.t('print.generating'), 'info');

    try {
      const pdf = generatePdf();
      pdf.save(`labels_${new Date().toISOString().slice(0, 10)}.pdf`);
      showToast(I18n.t('print.generated'), 'success');
    } catch (e) {
      console.error('[Printer] PDF error:', e);
      showToast(e.message, 'error');
    }
  }

  function directPrint() {
    try {
      const pdf = generatePdf();
      const blob = pdf.output('blob');
      const url = URL.createObjectURL(blob);
      const printWindow = window.open(url);
      if (printWindow) {
        printWindow.addEventListener('load', () => {
          printWindow.print();
        });
      }
    } catch (e) {
      console.error('[Printer] Print error:', e);
      showToast(e.message, 'error');
    }
  }

  function generatePdf() {
    const { jsPDF } = window.jspdf;
    const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });

    const s = printSettings;
    const perPage = s.cols * s.rows;
    const totalPages = getTotalPrintPages();
    const columns = Table.getColumns().filter((c) => c.visible !== false);
    const offset = s.startPos - 1;

    for (let page = 0; page < totalPages; page++) {
      if (page > 0) pdf.addPage();

      const pageStart = page * perPage - offset;

      for (let row = 0; row < s.rows; row++) {
        for (let col = 0; col < s.cols; col++) {
          const slotIndex = row * s.cols + col;
          const itemIndex = pageStart + slotIndex;
          if (itemIndex < 0 || itemIndex >= printItems.length) continue;

          const item = printItems[itemIndex];
          const x = s.marginLeft + col * (s.labelW + s.gapH);
          const y = s.marginTop + row * (s.labelH + s.gapV);

          renderLabelToPdf(pdf, item, columns, x, y, s);
        }
      }
    }

    return pdf;
  }

  function renderLabelToPdf(pdf, item, columns, x, y, s) {
    const padding = 1.5;
    let cursorY = y + padding;
    const maxY = y + s.labelH - padding;
    const fontSize = s.fontSize === 'auto' ? 8 : parseInt(s.fontSize, 10);

    columns.forEach((col) => {
      if (cursorY >= maxY) return;
      const mode = s.columnDisplay[col.key] || 'text';
      if (mode === 'hidden') return;

      const val = String(item[col.key] ?? '');

      if (mode === 'barcode' && val) {
        // SVGバーコード → PDF画像
        try {
          const svgNS = 'http://www.w3.org/2000/svg';
          const svg = document.createElementNS(svgNS, 'svg');
          JsBarcode(svg, val, {
            format: s.barcodeFormat === 'qr' ? 'CODE128' : s.barcodeFormat,
            width: 1.5,
            height: s.barcodeHeight * 0.8,
            displayValue: s.showText,
            fontSize: 10,
            margin: 0,
          });

          const svgData = new XMLSerializer().serializeToString(svg);
          const svgB64 = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgData)));

          const barcodeW = Math.min(s.labelW - padding * 2, s.labelW * 0.9);
          pdf.addSvgAsImage(svgData, x + padding, cursorY, barcodeW, s.barcodeHeight * 0.8);
          cursorY += s.barcodeHeight + 1;
        } catch {
          pdf.setFontSize(fontSize);
          pdf.text(`[${val}]`, x + padding, cursorY + fontSize * 0.35);
          cursorY += fontSize * 0.4 + 1;
        }
      } else if (mode === 'labelText') {
        pdf.setFontSize(fontSize * 0.8);
        pdf.setTextColor(100);
        pdf.text(`${col.name}: `, x + padding, cursorY + fontSize * 0.35);
        const labelW = pdf.getTextWidth(`${col.name}: `);
        pdf.setTextColor(0);
        pdf.setFontSize(fontSize);
        pdf.text(val, x + padding + labelW, cursorY + fontSize * 0.35);
        cursorY += fontSize * 0.4 + 1;
      } else if (mode === 'text') {
        pdf.setFontSize(fontSize);
        pdf.setTextColor(0);
        const lines = pdf.splitTextToSize(val, s.labelW - padding * 2);
        lines.slice(0, 3).forEach((line) => {
          if (cursorY + fontSize * 0.35 < maxY) {
            pdf.text(line, x + padding, cursorY + fontSize * 0.35);
            cursorY += fontSize * 0.4 + 0.5;
          }
        });
      }
    });
  }

  // --- サイドバーバーコードプレビュー ---
  function updateSidebarPreview() {
    const input = document.getElementById('scan-input');
    const previewArea = document.getElementById('barcode-preview');
    if (!input || !previewArea) return;

    const value = input.value.trim();
    if (!value) {
      previewArea.innerHTML = '<p style="color:var(--color-text-muted);font-size:12px;">—</p>';
      document.getElementById('btn-barcode-print').disabled = true;
      document.getElementById('btn-barcode-save').disabled = true;
      return;
    }

    previewArea.innerHTML = '<svg id="sidebar-barcode"></svg>';
    try {
      JsBarcode('#sidebar-barcode', value, {
        format: printSettings.barcodeFormat || 'CODE128',
        width: 2,
        height: 60,
        displayValue: true,
        fontSize: 14,
        margin: 4,
      });
      document.getElementById('btn-barcode-print').disabled = false;
      document.getElementById('btn-barcode-save').disabled = false;
    } catch {
      previewArea.innerHTML = '<p style="color:var(--color-danger);font-size:12px;">Invalid barcode</p>';
    }
  }

  // 行選択時のプレビュー更新
  function previewItemBarcode(item) {
    const previewArea = document.getElementById('barcode-preview');
    if (!previewArea || !item) return;

    const barcodeCol = printSettings.barcodeCol || Table.getColumns()[0]?.key;
    const value = item[barcodeCol];
    if (!value) return;

    previewArea.innerHTML = '<svg id="sidebar-barcode"></svg>';
    try {
      JsBarcode('#sidebar-barcode', String(value), {
        format: printSettings.barcodeFormat || 'CODE128',
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

  return {
    init,
    openPrintModal,
    closePrintModal,
    updateSidebarPreview,
    previewItemBarcode,
  };
})();

if (typeof module !== 'undefined' && module.exports) {
  module.exports = Printer;
}
