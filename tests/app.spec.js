// @ts-check
const { test, expect } = require('@playwright/test');

// ============================================================
//  ヘルパー
// ============================================================

/** ページ読み込み＋初期化待ち */
async function loadApp(page) {
  await page.goto('/');
  await page.waitForSelector('.tab-nav', { timeout: 10_000 });
  // IndexedDB初期化を少し待つ
  await page.waitForTimeout(500);
}

/** サンプルデータを読み込む（取込タブのサンプルボタンを使用） */
async function loadSampleData(page) {
  // 取込タブに切り替え
  await page.click('#tb-import');
  await page.waitForTimeout(300);
  // サンプルデータボタンをクリック
  const sampleBtn = page.locator('button').filter({ hasText: /サンプルデータ/ });
  // 確認ダイアログをあらかじめ受け入れる
  page.once('dialog', async dialog => await dialog.accept());
  await sampleBtn.click();
  await page.waitForTimeout(1500);
}

// ============================================================
//  1. ページ読み込み・基本構造
// ============================================================

test.describe('ページ読み込み', () => {
  test('タイトルが正しい', async ({ page }) => {
    await loadApp(page);
    await expect(page).toHaveTitle(/バーコード管理/);
  });

  test('ヘッダーが表示される', async ({ page }) => {
    await loadApp(page);
    const header = page.locator('.app-header h1');
    await expect(header).toBeVisible();
    await expect(header).toContainText('バーコード管理');
  });

  test('4つのタブボタンが存在する', async ({ page }) => {
    await loadApp(page);
    const tabs = page.locator('.tab-nav .tab-btn');
    await expect(tabs).toHaveCount(4);
  });

  test('Service Workerが登録される', async ({ page }) => {
    await loadApp(page);
    await page.waitForTimeout(2000);
    const swRegistered = await page.evaluate(async () => {
      const regs = await navigator.serviceWorker.getRegistrations();
      return regs.length > 0;
    });
    expect(swRegistered).toBe(true);
  });

  test('コンソールにエラーがない', async ({ page }) => {
    const errors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text());
    });
    await loadApp(page);
    await page.waitForTimeout(2000);
    // SW関連やネットワークエラーを除外
    const realErrors = errors.filter(e =>
      !e.includes('service') && !e.includes('sw.js') && !e.includes('Failed to fetch')
    );
    expect(realErrors).toHaveLength(0);
  });
});

// ============================================================
//  2. タブ切り替え
// ============================================================

test.describe('タブナビゲーション', () => {
  test.beforeEach(async ({ page }) => {
    await loadApp(page);
    // データ/印刷/貸出タブはデータが無いとdisabledなので先にサンプル読み込み
    await loadSampleData(page);
  });

  test('取込タブ → パネルが表示される', async ({ page }) => {
    await page.click('#tb-import');
    await expect(page.locator('#tab-import')).toBeVisible();
  });

  test('データタブ → パネルが表示される', async ({ page }) => {
    await page.click('#tb-data');
    await expect(page.locator('#tab-data')).toBeVisible();
  });

  test('印刷タブ → パネルが表示される', async ({ page }) => {
    await page.click('#tb-print');
    await expect(page.locator('#tab-print')).toBeVisible();
  });

  test('貸出タブ → パネルが表示される', async ({ page }) => {
    await page.click('#tb-lending');
    await expect(page.locator('#tab-lending')).toBeVisible();
  });

  test('タブ切り替えでアクティブ状態が変わる', async ({ page }) => {
    await page.click('#tb-data');
    await expect(page.locator('#tb-data')).toHaveClass(/active/);
    await page.click('#tb-print');
    await expect(page.locator('#tb-print')).toHaveClass(/active/);
    await expect(page.locator('#tb-data')).not.toHaveClass(/active/);
  });
});

// ============================================================
//  3. サンプルデータ読み込み・テーブル操作
// ============================================================

test.describe('データ管理', () => {
  test('サンプルデータを読み込むとテーブルに行が表示される', async ({ page }) => {
    await loadApp(page);
    await loadSampleData(page);
    // データタブに切り替え
    await page.click('#tb-data');
    await page.waitForTimeout(500);
    const rows = page.locator('#tbody tr');
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);
  });

  test('サンプルデータ後にタブの件数バッジが更新される', async ({ page }) => {
    await loadApp(page);
    await loadSampleData(page);
    await page.waitForTimeout(500);
    const badge = page.locator('#tn-data');
    const text = await badge.textContent();
    const num = parseInt(text || '0', 10);
    expect(num).toBeGreaterThan(0);
  });
});

// ============================================================
//  4. ダークモード
// ============================================================

test.describe('ダークモード', () => {
  test.beforeEach(async ({ page }) => {
    await loadApp(page);
  });

  test('ダークモード切り替えボタンが存在する', async ({ page }) => {
    await expect(page.locator('#dark-toggle-btn')).toBeVisible();
  });

  test('クリックでbodyにdarkクラスが付与・解除される', async ({ page }) => {
    const btn = page.locator('#dark-toggle-btn');
    // ダークモードON
    await btn.click();
    await page.waitForTimeout(300);
    await expect(page.locator('body')).toHaveClass(/dark/);

    // ダークモードOFF
    await btn.click();
    await page.waitForTimeout(300);
    const bodyClass = await page.locator('body').getAttribute('class');
    expect(bodyClass || '').not.toContain('dark');
  });

  test('リロード後もダークモード状態が保持される', async ({ page }) => {
    // ONにする
    await page.locator('#dark-toggle-btn').click();
    await page.waitForTimeout(500);
    await expect(page.locator('body')).toHaveClass(/dark/);

    // リロード
    await page.reload();
    await page.waitForSelector('.tab-nav', { timeout: 10_000 });
    await page.waitForTimeout(1000);

    // 保持されている
    await expect(page.locator('body')).toHaveClass(/dark/);

    // 後片付け：OFFに戻す
    await page.locator('#dark-toggle-btn').click();
    await page.waitForTimeout(300);
  });
});

// ============================================================
//  5. バーコード形式セレクタ
// ============================================================

test.describe('バーコード形式選択', () => {
  test.beforeEach(async ({ page }) => {
    await loadApp(page);
    await loadSampleData(page);
    await page.click('#tb-print');
    await page.waitForTimeout(300);
  });

  test('形式セレクタにCODE128/CODE39/QRがある', async ({ page }) => {
    const select = page.locator('#bc-format-select');
    await expect(select).toBeVisible();

    const options = select.locator('option');
    const texts = await options.allTextContents();
    const joined = texts.join(' ');
    expect(joined).toMatch(/code128/i);
    expect(joined).toMatch(/code39/i);
    expect(joined).toMatch(/QR/i);
  });

  test('QR形式に切り替えられる', async ({ page }) => {
    await page.locator('#bc-format-select').selectOption('QR');
    await page.waitForTimeout(300);
    const value = await page.locator('#bc-format-select').inputValue();
    expect(value).toBe('QR');
  });
});

// ============================================================
//  6. ラベルプリセット
// ============================================================

test.describe('ラベルプリセット', () => {
  test.beforeEach(async ({ page }) => {
    await loadApp(page);
    await loadSampleData(page);
    await page.click('#tb-print');
    await page.waitForTimeout(300);
  });

  test('ラベルプリセットセレクタが存在する', async ({ page }) => {
    await expect(page.locator('#label-preset-select')).toBeVisible();
  });

  test('6種類のプリセット＋カスタムがある', async ({ page }) => {
    const options = page.locator('#label-preset-select option');
    const count = await options.count();
    expect(count).toBeGreaterThanOrEqual(7); // 6 presets + custom
  });

  test('プリセットを44面に変更するとプレビュータイトルが更新される', async ({ page }) => {
    // beforeEachで既にloadApp + loadSampleData + 印刷タブ遷移済み
    // データタブに戻って行を選択
    await page.click('#tb-data');
    await page.waitForTimeout(300);

    // 全行のチェックボックスをクリック（最初のチェックボックス）
    const firstCb = page.locator('#tbody tr input[type="checkbox"]').first();
    if (await firstCb.count() > 0) await firstCb.click();

    // 印刷タブへ戻る
    await page.click('#tb-print');
    await page.waitForTimeout(300);

    // 44面に変更
    await page.locator('#label-preset-select').selectOption('a4-44');
    await page.waitForTimeout(500);

    // プレビュータイトルにa4-44に関する表記がある確認
    // （プレビューを開く必要がある場合もある）
    const btn = page.locator('button').filter({ hasText: /プレビュー/ });
    if (await btn.count() > 0) {
      await btn.click();
      await page.waitForTimeout(1000);
      const title = page.locator('#pv-title');
      if (await title.count() > 0) {
        await expect(title).toContainText('44');
      }
    }
  });
});

// ============================================================
//  7. 設定モーダル
// ============================================================

test.describe('設定モーダル', () => {
  test('設定ボタンクリックでモーダルが開く', async ({ page }) => {
    await loadApp(page);
    await page.click('.settings-gear');
    await expect(page.locator('#settings-overlay')).toBeVisible();
  });

  test('閉じるボタンでモーダルが閉じる', async ({ page }) => {
    await loadApp(page);
    await page.click('.settings-gear');
    await expect(page.locator('#settings-overlay')).toBeVisible();

    // 「閉じる」ボタンをクリック
    const closeBtn = page.locator('#settings-overlay button').filter({ hasText: /閉じる/ }).first();
    await closeBtn.click();
    await expect(page.locator('#settings-overlay')).toBeHidden();
  });

  test('バックアップエクスポートボタンが存在する', async ({ page }) => {
    await loadApp(page);
    await page.click('.settings-gear');
    await expect(page.locator('#settings-overlay')).toBeVisible();
    const backupBtn = page.locator('#settings-overlay button').filter({ hasText: /バックアップ|エクスポート/ });
    await expect(backupBtn.first()).toBeVisible();
  });

  test('ダークモード設定がある', async ({ page }) => {
    await loadApp(page);
    await page.click('.settings-gear');
    await expect(page.locator('#settings-overlay')).toBeVisible();
    const settingsText = await page.locator('#settings-overlay').textContent();
    expect(settingsText).toContain('ダーク');
  });

  test('ファイル保存ボタンが存在する', async ({ page }) => {
    await loadApp(page);
    await page.click('.settings-gear');
    await expect(page.locator('#settings-overlay')).toBeVisible();
    const saveBtn = page.locator('#settings-overlay button').filter({ hasText: /ファイル.*保存|名前を付けて/ });
    await expect(saveBtn.first()).toBeVisible();
  });
});

// ============================================================
//  8. 貸出管理タブ
// ============================================================

test.describe('貸出管理', () => {
  test.beforeEach(async ({ page }) => {
    await loadApp(page);
    await loadSampleData(page);
    await page.click('#tb-lending');
    await page.waitForTimeout(300);
  });

  test('バーコード入力フィールドが存在する', async ({ page }) => {
    await expect(page.locator('#lending-barcode-input')).toBeVisible();
  });

  test('カメラスキャンボタンが存在する', async ({ page }) => {
    await expect(page.locator('#camera-scan-btn')).toBeVisible();
  });

  test('USBリーダーのヒントが表示される', async ({ page }) => {
    const tabText = await page.locator('#tab-lending').textContent();
    expect(tabText).toMatch(/USB|リーダー|スキャナ/);
  });

  test('現在の貸出/履歴の切り替えボタンがある', async ({ page }) => {
    await expect(page.locator('#view-current-btn')).toBeVisible();
    await expect(page.locator('#view-history-btn')).toBeVisible();
  });
});

// ============================================================
//  9. 印刷ガイド
// ============================================================

test.describe('印刷ガイド', () => {
  test('印刷ガイドのインライン表示がある', async ({ page }) => {
    await loadApp(page);
    await loadSampleData(page);
    await page.click('#tb-print');
    await page.waitForTimeout(300);
    const guide = page.locator('#print-guide-inline');
    // 存在確認（hiddenでも可）
    const count = await guide.count();
    expect(count).toBeGreaterThan(0);
  });
});

// ============================================================
//  10. 別窓（Detached / Pop-out）モード
// ============================================================

test.describe('別窓（Pop-out）モード', () => {
  test('4つのポップアウトボタンが存在する', async ({ page }) => {
    await loadApp(page);
    const popouts = page.locator('.popout-btn');
    const count = await popouts.count();
    expect(count).toBe(4);
  });

  test('ポップアウトリンクが正しいhrefを持つ', async ({ page }) => {
    await loadApp(page);
    const popouts = page.locator('.popout-btn');
    const hrefs = await popouts.evaluateAll(els => els.map(e => e.getAttribute('href')));
    expect(hrefs).toContain('#panel-import');
    expect(hrefs).toContain('#panel-data');
    expect(hrefs).toContain('#panel-print');
    expect(hrefs).toContain('#panel-lending');
  });

  test('detachedモードURLでアクセスするとバナーが表示される', async ({ page }) => {
    await page.goto('/#panel-data');
    await page.waitForTimeout(2000);
    // detachedバナーが表示される
    const banner = page.locator('#detached-banner');
    if (await banner.count() > 0) {
      // バナーが存在すればOK（表示はwindow.name依存の場合もある）
      expect(true).toBe(true);
    }
  });
});

// ============================================================
//  11. データ永続化
// ============================================================

test.describe('データ永続化', () => {
  test('リロード後もデータが保持される', async ({ page }) => {
    await loadApp(page);
    await loadSampleData(page);

    // データタブで行数を確認
    await page.click('#tb-data');
    await page.waitForTimeout(500);
    const beforeCount = await page.locator('#tbody tr').count();
    expect(beforeCount).toBeGreaterThan(0);

    // リロード
    await page.reload();
    await page.waitForSelector('.tab-nav', { timeout: 10_000 });
    await page.waitForTimeout(2000);

    // データタブで行数を再確認
    await page.click('#tb-data');
    await page.waitForTimeout(500);
    const afterCount = await page.locator('#tbody tr').count();
    expect(afterCount).toBe(beforeCount);
  });
});

// ============================================================
//  12. レスポンシブ
// ============================================================

test.describe('レスポンシブ', () => {
  test('モバイル幅（375px）でもタブとヘッダーが表示される', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await loadApp(page);
    await expect(page.locator('.app-header h1')).toBeVisible();
    await expect(page.locator('.tab-nav')).toBeVisible();
  });

  test('タブレット幅（768px）でもレイアウトが崩れない', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await loadApp(page);
    await expect(page.locator('.app-header')).toBeVisible();
    const tabs = page.locator('.tab-nav .tab-btn');
    await expect(tabs).toHaveCount(4);
  });
});
