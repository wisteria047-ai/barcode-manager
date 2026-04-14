// importer — CSV/Excel取込モジュール
const Importer = (() => {
  const SUPPORTED_EXTENSIONS = ['csv', 'xlsx', 'xls'];

  function init() {
    bindDropZone();
    bindFileInput();
    bindImportModal();
  }

  function bindDropZone() {
    const tableContainer = document.getElementById('table-container');
    if (!tableContainer) return;

    tableContainer.addEventListener('dragover', (e) => {
      e.preventDefault();
      tableContainer.classList.add('drag-over');
    });
    tableContainer.addEventListener('dragleave', () => {
      tableContainer.classList.remove('drag-over');
    });
    tableContainer.addEventListener('drop', (e) => {
      e.preventDefault();
      tableContainer.classList.remove('drag-over');
      const files = e.dataTransfer?.files;
      if (files?.length > 0) processFile(files[0]);
    });

    // import-drop-zone（モーダル内）
    const dropZone = document.getElementById('import-drop-zone');
    if (!dropZone) return;

    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropZone.classList.add('drag-over');
    });
    dropZone.addEventListener('dragleave', () => {
      dropZone.classList.remove('drag-over');
    });
    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZone.classList.remove('drag-over');
      const files = e.dataTransfer?.files;
      if (files?.length > 0) processFile(files[0]);
    });
  }

  function bindFileInput() {
    const fileInput = document.getElementById('file-input');
    const selectBtn = document.getElementById('btn-select-file');

    selectBtn?.addEventListener('click', () => fileInput?.click());
    fileInput?.addEventListener('change', (e) => {
      if (e.target.files?.length > 0) {
        processFile(e.target.files[0]);
        e.target.value = '';
      }
    });
  }

  function bindImportModal() {
    document.getElementById('btn-download-template')?.addEventListener('click', (e) => {
      e.preventDefault();
      downloadTemplate();
    });
  }

  // --- ファイル処理 ---
  async function processFile(file) {
    const ext = file.name.split('.').pop().toLowerCase();

    if (!SUPPORTED_EXTENSIONS.includes(ext)) {
      showToast(I18n.t('import.unsupportedFormat', { ext }), 'error');
      return;
    }

    showToast(I18n.t('import.importing'), 'info');

    try {
      const data = await readFile(file, ext);
      if (data.length === 0) {
        showToast(I18n.t('import.unsupportedFormat', { ext }), 'error');
        return;
      }

      // 文字化け検出
      if (hasEncodingIssue(data)) {
        showToast(I18n.t('import.encodingError'), 'error');
        // Shift_JIS で再試行
        const retryData = await readFile(file, ext, 'Shift_JIS');
        if (retryData.length > 0 && !hasEncodingIssue(retryData)) {
          await importData(retryData);
          return;
        }
      }

      await importData(data);
    } catch (err) {
      console.error('[Importer] Error:', err);
      showToast(err.message, 'error');
    }
  }

  async function readFile(file, ext, encoding) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();

      reader.onload = (e) => {
        try {
          if (ext === 'csv') {
            const text = e.target.result;
            resolve(parseCsv(text));
          } else {
            const data = new Uint8Array(e.target.result);
            const workbook = XLSX.read(data, { type: 'array' });
            const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
            const json = XLSX.utils.sheet_to_json(firstSheet, { defval: '' });
            resolve(json);
          }
        } catch (err) {
          reject(err);
        }
      };

      reader.onerror = () => reject(new Error('File read error'));

      if (ext === 'csv') {
        reader.readAsText(file, encoding || 'UTF-8');
      } else {
        reader.readAsArrayBuffer(file);
      }
    });
  }

  function parseCsv(text) {
    const lines = text.trim().split(/\r?\n/);
    if (lines.length < 2) return [];

    const headers = parseCSVLine(lines[0]);
    const data = [];

    for (let i = 1; i < lines.length; i++) {
      const values = parseCSVLine(lines[i]);
      if (values.length === 0) continue;
      const row = {};
      headers.forEach((h, j) => {
        row[h.trim()] = (values[j] || '').trim();
      });
      data.push(row);
    }
    return data;
  }

  // RFC 4180 準拠の CSV パーサー
  function parseCSVLine(line) {
    const result = [];
    let current = '';
    let inQuotes = false;

    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (inQuotes) {
        if (ch === '"') {
          if (i + 1 < line.length && line[i + 1] === '"') {
            current += '"';
            i++;
          } else {
            inQuotes = false;
          }
        } else {
          current += ch;
        }
      } else {
        if (ch === '"') {
          inQuotes = true;
        } else if (ch === ',') {
          result.push(current);
          current = '';
        } else {
          current += ch;
        }
      }
    }
    result.push(current);
    return result;
  }

  function hasEncodingIssue(data) {
    const sample = JSON.stringify(data.slice(0, 5));
    // 文字化け特有のパターン
    return /\ufffd/.test(sample) || /[\x80-\x9f]/.test(sample);
  }

  async function importData(data) {
    await Storage.addItems(data);
    closeImportModal();
    await Table.loadData();
    showToast(I18n.t('import.imported', { count: data.length }), 'success');
  }

  // --- テンプレートダウンロード ---
  function downloadTemplate() {
    const headers = I18n.t('import.templateHeaders').split(',');
    const bom = '\uFEFF';
    const csv = bom + headers.join(',') + '\n';
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'template.csv';
    a.click();
    URL.revokeObjectURL(url);
  }

  // --- CSVエクスポート ---
  function exportCsv() {
    const items = Table.getItems();
    const cols = Table.getColumns().filter((c) => c.visible !== false);

    if (items.length === 0) return;

    const bom = '\uFEFF';
    const headers = cols.map((c) => c.name);
    let csv = bom + headers.map(escapeCsvField).join(',') + '\n';

    items.forEach((item) => {
      const row = cols.map((c) => escapeCsvField(String(item[c.key] ?? '')));
      csv += row.join(',') + '\n';
    });

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `export_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);

    showToast(I18n.t('import.imported', { count: items.length }), 'success');
  }

  function escapeCsvField(str) {
    if (/[,"\n\r]/.test(str)) {
      return '"' + str.replace(/"/g, '""') + '"';
    }
    return str;
  }

  // --- モーダル制御 ---
  function openImportModal() {
    document.getElementById('import-modal')?.classList.add('visible');
  }

  function closeImportModal() {
    document.getElementById('import-modal')?.classList.remove('visible');
  }

  return {
    init,
    openImportModal,
    closeImportModal,
    exportCsv,
    downloadTemplate,
    processFile,
  };
})();

if (typeof module !== 'undefined' && module.exports) {
  module.exports = Importer;
}
