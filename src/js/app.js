// app — メインエントリ・初期化・グローバルイベント

// サンプルデータ（12行の文房具）
const SAMPLE_DATA = [
  { '管理番号': 'BN-001', '品名': 'ボールペン（黒）', 'カテゴリ': '筆記用具', '保管場所': 'A棚-1段', '数量': '50', '備考': '' },
  { '管理番号': 'BN-002', '品名': 'ボールペン（赤）', 'カテゴリ': '筆記用具', '保管場所': 'A棚-1段', '数量': '30', '備考': '' },
  { '管理番号': 'BN-003', '品名': 'シャープペンシル', 'カテゴリ': '筆記用具', '保管場所': 'A棚-1段', '数量': '20', '備考': '0.5mm' },
  { '管理番号': 'BN-004', '品名': '消しゴム', 'カテゴリ': '筆記用具', '保管場所': 'A棚-2段', '数量': '40', '備考': '' },
  { '管理番号': 'BN-005', '品名': 'ノート A4', 'カテゴリ': 'ノート', '保管場所': 'B棚-1段', '数量': '25', '備考': '罫線' },
  { '管理番号': 'BN-006', '品名': 'ノート B5', 'カテゴリ': 'ノート', '保管場所': 'B棚-1段', '数量': '15', '備考': '方眼' },
  { '管理番号': 'BN-007', '品名': 'クリアファイル', 'カテゴリ': 'ファイル', '保管場所': 'B棚-2段', '数量': '100', '備考': 'A4サイズ' },
  { '管理番号': 'BN-008', '品名': 'ホッチキス', 'カテゴリ': '綴じ具', '保管場所': 'C棚-1段', '数量': '10', '備考': '' },
  { '管理番号': 'BN-009', '品名': 'ホッチキス針', 'カテゴリ': '綴じ具', '保管場所': 'C棚-1段', '数量': '20', '備考': 'No.10' },
  { '管理番号': 'BN-010', '品名': 'セロテープ', 'カテゴリ': 'テープ', '保管場所': 'C棚-2段', '数量': '15', '備考': '15mm幅' },
  { '管理番号': 'BN-011', '品名': 'はさみ', 'カテゴリ': '切断', '保管場所': 'C棚-2段', '数量': '8', '備考': '' },
  { '管理番号': 'BN-012', '品名': '付箋（大）', 'カテゴリ': 'メモ', '保管場所': 'A棚-3段', '数量': '30', '備考': '75×75mm' },
];

// --- UI委譲（後方互換グローバル関数） ---
function showToast(message, type, duration) { UI.showToast(message, type, duration); }
function showUndo(message, onUndo) { UI.showUndo(message, onUndo); }
function showConfirm(title, body, okLabel, onOk) { UI.showConfirm(title, body, okLabel, onOk); }

// --- 設定パネル ---
function openSettings() {
  // 既存があれば閉じる
  closeSettings();

  const overlay = document.createElement('div');
  overlay.className = 'settings-overlay';
  overlay.id = 'settings-overlay';
  overlay.addEventListener('click', closeSettings);

  const panel = document.createElement('div');
  panel.className = 'settings-panel';
  panel.id = 'settings-panel';

  const currentLang = I18n.getLang();
  panel.innerHTML = `
    <h3 style="margin-bottom: 20px;">${I18n.t('settings.title')}</h3>
    <div class="settings-group">
      <label>${I18n.t('settings.language')}</label>
      <select id="setting-language">
        <option value="ja" ${currentLang === 'ja' ? 'selected' : ''}>${I18n.t('settings.japanese')}</option>
        <option value="en" ${currentLang === 'en' ? 'selected' : ''}>${I18n.t('settings.english')}</option>
      </select>
    </div>
    <div class="settings-group">
      <label>${I18n.t('settings.fontSize')}</label>
      <input type="range" id="setting-font-size" min="12" max="18" value="${parseInt(getComputedStyle(document.documentElement).fontSize, 10) || 14}">
      <span id="font-size-display">${parseInt(getComputedStyle(document.documentElement).fontSize, 10) || 14}px</span>
    </div>
    <div class="settings-group" style="margin-top: 24px;">
      <button class="btn btn--secondary" id="btn-manage-operators" style="width:100%;margin-bottom:8px;">${I18n.t('operator.manage')}</button>
      <button class="btn btn--secondary" id="btn-reset-layout" style="width:100%;">${I18n.t('settings.resetLayout')}</button>
    </div>
  `;

  document.body.appendChild(overlay);
  document.body.appendChild(panel);

  // 言語切替
  document.getElementById('setting-language').addEventListener('change', async (e) => {
    await I18n.setLang(e.target.value);
    await Storage.setSetting('language', e.target.value);
    I18n.translatePage();
    Table.render();
    closeSettings();
    openSettings(); // 設定パネル自体も再描画
  });

  // フォントサイズ
  document.getElementById('setting-font-size').addEventListener('input', async (e) => {
    const size = e.target.value;
    document.documentElement.style.fontSize = `${size}px`;
    document.getElementById('font-size-display').textContent = `${size}px`;
    await Storage.setSetting('fontSize', parseInt(size, 10));
  });

  // 操作者管理
  document.getElementById('btn-manage-operators').addEventListener('click', () => {
    closeSettings();
    Scanner.showOperatorManager();
  });

  // レイアウトリセット
  document.getElementById('btn-reset-layout').addEventListener('click', () => {
    showConfirm(
      I18n.t('settings.resetConfirm'),
      '',
      I18n.t('settings.resetLayout'),
      async () => {
        document.documentElement.style.fontSize = '14px';
        document.getElementById('scan-panel').style.width = '';
        await Storage.setSetting('fontSize', 14);
        await Storage.setSetting('panelWidth', null);
        closeSettings();
        Table.render();
      }
    );
  });

  // ESCで閉じる
  const onKey = (e) => {
    if (e.key === 'Escape') { closeSettings(); document.removeEventListener('keydown', onKey); }
  };
  document.addEventListener('keydown', onKey);
}

function closeSettings() {
  document.getElementById('settings-overlay')?.remove();
  document.getElementById('settings-panel')?.remove();
}

// --- スプリッター ---
function initSplitter() {
  const splitter = document.getElementById('splitter');
  const panel = document.getElementById('scan-panel');
  if (!splitter || !panel) return;

  let startX, startWidth;

  splitter.addEventListener('mousedown', (e) => {
    e.preventDefault();
    startX = e.clientX;
    startWidth = panel.offsetWidth;

    const onMove = (e) => {
      const diff = startX - e.clientX;
      const newWidth = Math.max(240, Math.min(window.innerWidth * 0.5, startWidth + diff));
      panel.style.width = `${newWidth}px`;
    };

    const onUp = async () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      await Storage.setSetting('panelWidth', panel.offsetWidth);
    };

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });
}

// --- パネル折りたたみ ---
function initPanelSections() {
  document.querySelectorAll('.panel-section-title').forEach((title) => {
    const toggle = () => {
      const section = title.closest('.panel-section');
      const collapsed = section.classList.toggle('collapsed');
      title.setAttribute('aria-expanded', String(!collapsed));
    };
    title.addEventListener('click', toggle);
    title.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        toggle();
      }
    });
  });
}

// --- 横スクロールヒント ---
function initScrollHint() {
  const container = document.getElementById('table-container');
  if (!container) return;

  const update = () => {
    const hasOverflow = container.scrollWidth > container.clientWidth;
    const atEnd = container.scrollLeft + container.clientWidth >= container.scrollWidth - 2;
    container.classList.toggle('has-scroll-right', hasOverflow && !atEnd);
  };

  container.addEventListener('scroll', update, { passive: true });
  new ResizeObserver(update).observe(container);
}

// --- パネルトグル ---
function initPanelToggle() {
  const btn = document.getElementById('btn-toggle-panel');
  const panel = document.getElementById('scan-panel');
  const splitter = document.getElementById('splitter');
  if (!btn || !panel) return;

  btn.addEventListener('click', async () => {
    const isHidden = panel.classList.toggle('panel-hidden');
    btn.textContent = isHidden ? '▶' : '◀';
    btn.setAttribute('aria-label', I18n.t(isHidden ? 'panel.toggleShow' : 'panel.toggleHide'));
    await Storage.setSetting('panelHidden', isHidden);
  });

  // 保存済み状態を復元
  Storage.getSetting('panelHidden', false).then((hidden) => {
    if (hidden) {
      panel.classList.add('panel-hidden');
      btn.textContent = '▶';
    }
  });
}

// --- アプリ初期化 ---
async function initApp() {
  // i18n初期化
  const savedLang = await Storage.getSetting('language', 'ja');
  await I18n.init(savedLang);
  await I18n.setLang(savedLang);
  I18n.translatePage();

  // 保存済みフォントサイズ復元
  const savedFontSize = await Storage.getSetting('fontSize', 14);
  document.documentElement.style.fontSize = `${savedFontSize}px`;

  // 保存済みパネル幅復元
  const savedPanelWidth = await Storage.getSetting('panelWidth', null);
  if (savedPanelWidth) {
    document.getElementById('scan-panel').style.width = `${savedPanelWidth}px`;
  }

  // テーブル初期化
  await Table.init();

  // インポーター初期化
  Importer.init();

  // プリンター初期化
  Printer.init();

  // スキャナー初期化
  Scanner.init();

  // スプリッター初期化
  initSplitter();

  // パネルセクション折りたたみ
  initPanelSections();

  // パネルトグルボタン
  initPanelToggle();

  // 横スクロールヒント
  initScrollHint();

  // ツールバーイベント
  document.getElementById('btn-import').addEventListener('click', Importer.openImportModal);
  document.getElementById('btn-close-import').addEventListener('click', Importer.closeImportModal);
  document.getElementById('btn-settings').addEventListener('click', openSettings);
  document.getElementById('btn-add-row').addEventListener('click', () => Table.addRow());
  document.getElementById('btn-export').addEventListener('click', Importer.exportCsv);

  // 空状態ボタン
  document.getElementById('btn-try-sample').addEventListener('click', loadSampleData);
  document.getElementById('btn-import-empty').addEventListener('click', Importer.openImportModal);

  // モーダル背景クリックで閉じる
  document.getElementById('import-modal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) Importer.closeImportModal();
  });
  document.getElementById('confirm-modal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) e.currentTarget.classList.remove('visible');
  });

  // i18n変更時にページ更新
  I18n.onChange(() => {
    I18n.translatePage();
    document.title = I18n.t('app.title');
    Table.loadData();
  });

  // グローバルキーボードショートカット
  document.addEventListener('keydown', (e) => {
    // Cmd+Z / Ctrl+Z: Undo（Undoバーが表示中なら実行）
    if ((e.metaKey || e.ctrlKey) && e.key === 'z' && !e.shiftKey) {
      const undoBar = document.getElementById('undo-bar');
      const undoBtn = document.getElementById('btn-undo');
      if (undoBar?.classList.contains('visible') && undoBtn) {
        e.preventDefault();
        undoBtn.click();
      }
    }
  });
}

// --- サンプルデータ読み込み ---
async function loadSampleData() {
  await Storage.clearItems();
  await Storage.addItems(SAMPLE_DATA);
  await Table.loadData();
  showToast(I18n.t('import.imported', { count: SAMPLE_DATA.length }), 'success');
}

// --- 起動 ---
document.addEventListener('DOMContentLoaded', initApp);
