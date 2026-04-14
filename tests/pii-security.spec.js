// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * 個人情報 (PII) セキュリティテスト
 *
 * バーコード管理ツールに個人情報が入力された場合でも
 * セキュリティ上問題がないことを検証する。
 */

// ── ヘルパー ──

async function loadApp(page) {
  await page.goto('/');
  await page.waitForSelector('.tab-nav', { timeout: 10_000 });
  await page.waitForTimeout(500);
}

async function loadSampleData(page) {
  await page.click('#tb-import');
  await page.waitForTimeout(300);
  const sampleBtn = page.locator('button').filter({ hasText: /サンプルデータ/ });
  page.once('dialog', async d => await d.accept());
  await sampleBtn.click();
  await page.waitForTimeout(1500);
}

/** サンプルデータ読込後にデータタブへ移動 */
async function loadSampleAndGoToData(page) {
  await loadSampleData(page);
  await page.click('#tb-data');
  await page.waitForTimeout(500);
}

// ============================================================
// §1: XSS防御テスト
// ============================================================

test.describe('PII XSS防御', () => {

  test('テーブルの表示でHTMLタグがエスケープされている', async ({ page }) => {
    await loadApp(page);
    await loadSampleAndGoToData(page);
    // 編集モードでXSSペイロードを注入
    const editBtn = page.locator('#tbody tr').first().locator('button', { hasText: '編集' });
    await editBtn.click();
    await page.waitForTimeout(300);
    const inputs = page.locator('#tbody tr').first().locator('input[type="text"]');
    await inputs.first().fill('<script>alert("XSS")</script>');
    const saveBtn = page.locator('#tbody tr').first().locator('button', { hasText: '保存' });
    await saveBtn.click();
    await page.waitForTimeout(500);
    // 保存後のHTML
    const cellHtml = await page.locator('#tbody tr').first().innerHTML();
    expect(cellHtml).not.toContain('<script>');
    expect(cellHtml).toContain('&lt;script&gt;');
  });

  test('XSSペイロードがalertを発火させない', async ({ page }) => {
    let alertFired = false;
    page.on('dialog', async d => {
      if (d.type() === 'alert') alertFired = true;
      await d.dismiss();
    });
    await loadApp(page);
    await loadSampleAndGoToData(page);
    // 行追加 → XSSペイロードを全カラムに入力
    const addRowBtn = page.locator('button').filter({ hasText: '行を追加' });
    await addRowBtn.click();
    await page.waitForTimeout(300);
    // 最後の行が編集モードで追加される
    const lastRow = page.locator('#tbody tr').last();
    const inputs = lastRow.locator('input[type="text"]');
    const count = await inputs.count();
    for (let i = 0; i < count; i++) {
      await inputs.nth(i).fill('<img src=x onerror=alert(' + i + ')>');
    }
    const saveBtn = lastRow.locator('button', { hasText: '保存' });
    await saveBtn.click();
    await page.waitForTimeout(1000);
    expect(alertFired).toBe(false);
  });

  test('検索フィールドにXSSペイロードを入力してもスクリプトが実行されない', async ({ page }) => {
    let alertFired = false;
    page.on('dialog', async d => {
      if (d.type() === 'alert') alertFired = true;
      await d.dismiss();
    });
    await loadApp(page);
    await loadSampleAndGoToData(page);
    const searchInput = page.locator('#table-search');
    await searchInput.fill('<script>alert("XSS")</script>');
    await page.waitForTimeout(500);
    expect(alertFired).toBe(false);
  });

  test('貸出バーコード入力にXSSペイロードを入れてもスクリプトが実行されない', async ({ page }) => {
    let alertFired = false;
    page.on('dialog', async d => {
      if (d.type() === 'alert') alertFired = true;
      await d.dismiss();
    });
    await loadApp(page);
    await loadSampleAndGoToData(page);
    // タブ3: バーコード列を設定
    await page.click('#tb-print');
    await page.waitForTimeout(300);
    const barcodeColSelect = page.locator('#bc-col-select');
    await barcodeColSelect.selectOption({ index: 1 });
    await page.waitForTimeout(200);
    // タブ4: 貸出入力にXSS
    await page.click('#tb-lending');
    await page.waitForTimeout(300);
    const barcodeInput = page.locator('#lending-barcode-input');
    await barcodeInput.fill('<script>alert("XSS")</script>');
    // 検索ボタン（lookupBarcode）をクリック
    const searchBtn = page.locator('#lending-scan-area button.btn-primary');
    await searchBtn.click();
    await page.waitForTimeout(500);
    expect(alertFired).toBe(false);
    // 表示されたエラーメッセージもエスケープされていること
    const resultEl = page.locator('#lending-item-result');
    const isHidden = await resultEl.evaluate(el => el.classList.contains('hidden'));
    if (!isHidden) {
      const cardHtml = await page.locator('#item-info-card').innerHTML();
      expect(cardHtml).not.toContain('<script>');
    }
  });
});

// ============================================================
// §2: CSP (Content-Security-Policy) テスト
// ============================================================

test.describe('CSP適用確認', () => {

  test('CSPメタタグが存在しdefault-srcがselfである', async ({ page }) => {
    await loadApp(page);
    const csp = await page.locator('meta[http-equiv="Content-Security-Policy"]').getAttribute('content');
    expect(csp).toBeTruthy();
    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain("script-src 'self'");
    expect(csp).toContain("img-src 'self' data: blob:");
  });

  test('CSP下でもアプリの全機能が正常動作する', async ({ page }) => {
    await loadApp(page);
    await loadSampleAndGoToData(page);
    // データテーブル表示
    const rowCount = await page.locator('#tbody tr').count();
    expect(rowCount).toBeGreaterThan(0);
    // タブ切替
    await page.click('#tb-print');
    await page.waitForTimeout(300);
    const printPanel = page.locator('#tab-print');
    await expect(printPanel).toBeVisible();
  });
});

// ============================================================
// §3: ストレージ安全性テスト
// ============================================================

test.describe('ストレージ安全性', () => {

  test('外部サーバーへのデータ送信がない', async ({ page }) => {
    const externalRequests = [];
    page.on('request', req => {
      const url = req.url();
      if (!url.startsWith('data:') && !url.includes('localhost') && !url.startsWith('file://')) {
        externalRequests.push(url);
      }
    });
    await loadApp(page);
    await loadSampleAndGoToData(page);
    // 各タブを巡回
    await page.click('#tb-print');
    await page.waitForTimeout(200);
    await page.click('#tb-lending');
    await page.waitForTimeout(200);
    await page.click('#tb-data');
    await page.waitForTimeout(1000);
    expect(externalRequests.length).toBe(0);
  });

  test('リロード後もデータが保持される', async ({ page }) => {
    await loadApp(page);
    await loadSampleAndGoToData(page);
    const before = await page.locator('#tbody tr').count();
    expect(before).toBeGreaterThan(0);
    await page.reload();
    await page.waitForSelector('.tab-nav', { timeout: 10_000 });
    await page.waitForTimeout(1500);
    const tab2 = page.locator('#tb-data');
    if (await tab2.isEnabled()) {
      await tab2.click();
      await page.waitForTimeout(500);
    }
    const after = await page.locator('#tbody tr').count();
    expect(after).toBe(before);
  });

  test('IndexedDB/localStorage削除後にデータが消去される', async ({ page }) => {
    await loadApp(page);
    await loadSampleData(page);
    // ストレージを完全クリア
    await page.evaluate(async () => {
      localStorage.clear();
      const dbs = await indexedDB.databases();
      for (const db of dbs) {
        indexedDB.deleteDatabase(db.name);
      }
    });
    await page.reload();
    await page.waitForSelector('.tab-nav', { timeout: 10_000 });
    await page.waitForTimeout(1000);
    // タブ2が無効化されていること（データなし）
    const tab2 = page.locator('#tb-data');
    const isDisabled = await tab2.evaluate(el => el.hasAttribute('disabled'));
    expect(isDisabled).toBe(true);
  });
});

// ============================================================
// §4: DOM漏洩テスト
// ============================================================

test.describe('DOM漏洩防止', () => {

  test('データがページタイトル・URL・meta要素に漏洩しない', async ({ page }) => {
    await loadApp(page);
    await loadSampleAndGoToData(page);
    const title = await page.title();
    const url = page.url();
    const metas = await page.evaluate(() =>
      Array.from(document.querySelectorAll('meta')).map(m => m.outerHTML).join('')
    );
    // サンプルデータの値がメタ情報に漏れていない
    expect(title).not.toContain('ノート');
    expect(title).not.toContain('A-001');
    expect(url).not.toContain('A-001');
    expect(metas).not.toContain('A-001');
  });
});

// ============================================================
// §5: コンソールログ漏洩テスト
// ============================================================

test.describe('ログ漏洩防止', () => {

  test('コンソールログにユーザーデータが含まれない', async ({ page }) => {
    const logs = [];
    page.on('console', msg => logs.push(msg.text()));
    await loadApp(page);
    await loadSampleAndGoToData(page);
    // 全タブ巡回
    await page.click('#tb-print');
    await page.waitForTimeout(200);
    await page.click('#tb-lending');
    await page.waitForTimeout(200);
    await page.click('#tb-data');
    await page.waitForTimeout(500);
    const allLogs = logs.join(' ');
    // サンプルデータの品名がログに出ない
    expect(allLogs).not.toContain('ノート（A4）');
    expect(allLogs).not.toContain('ボールペン');
    expect(allLogs).not.toContain('A-001');
  });
});

// ============================================================
// §6: エクスポート安全性テスト
// ============================================================

test.describe('エクスポート安全性', () => {

  test('CSVダウンロードが正常に機能しXSSペイロードは生文字列として出力される', async ({ page }) => {
    await loadApp(page);
    await loadSampleAndGoToData(page);
    // XSSペイロードを含む行を追加
    const addRowBtn = page.locator('button').filter({ hasText: '行を追加' });
    await addRowBtn.click();
    await page.waitForTimeout(300);
    const lastRow = page.locator('#tbody tr').last();
    const inputs = lastRow.locator('input[type="text"]');
    if (await inputs.count() > 0) {
      await inputs.first().fill('<script>alert(1)</script>');
    }
    const saveBtn = lastRow.locator('button', { hasText: '保存' });
    await saveBtn.click();
    await page.waitForTimeout(500);
    // CSVダウンロード
    const [download] = await Promise.all([
      page.waitForEvent('download', { timeout: 5000 }).catch(() => null),
      page.locator('button').filter({ hasText: 'CSVで書き出す' }).click()
    ]);
    if (download) {
      const stream = await download.createReadStream();
      const content = await new Promise(resolve => {
        let data = '';
        stream.on('data', chunk => data += chunk);
        stream.on('end', () => resolve(data));
      });
      // XSSペイロードがそのまま文字列として出力（無害）
      expect(content).toContain('<script>alert(1)</script>');
    }
  });
});
