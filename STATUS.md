# STATUS — バーコード管理ツール v3.0

## 今やること
Phase 5 完了。出荷準備（ビルド確認・最終テスト）を行う。

## ここまでの成果

### Phase 1〜3: 全24タスク完了 ✅
- 1画面レイアウト（ツールバー/テーブル/スキャンパネル/ステータスバー）
- IndexedDB永続化（Dexie.js）、i18n（日本語/英語）
- CSV/Excel取込、テーブル表示・インライン編集・ソート・ページネーション
- バーコード生成（Code128/Code39/QR）、ラベル印刷（PDF出力）
- スキャン（即時反映/一括モード）、貸出/返却フロー、操作者管理

### Phase 4: 振り返り + リファクタリング ✅
- SheetJS バグ修正（Excel取込が壊れていた → scriptタグ追加）
- CDN 読込チェック（オフライン時エラーバナー）
- ui.js 新規抽出（showToast/showUndo/showConfirm/escapeHtml集約 + トースト重複排除）
- アクセシビリティ補完（全モーダル aria属性、テーブル caption/scope、sr-only）
- テスト 35件追加（i18n 10 + importer 25、全パス）
- UX改善（Cmd+Z、フォーカストラップ）

### Phase 5 Task 31: Android（Capacitor + カメラスキャン） ✅（2026-04-13）
- Capacitor v8 セットアップ、カメラスキャンUI、モバイルレスポンシブCSS
- テスト 23件追加（platform 12 + scanner-camera 11）

### Phase 5 CDN → ローカルバンドル化 ✅（2026-04-13）
- 5ライブラリ（Dexie, SheetJS, JsBarcode, QRCode, jsPDF）を src/vendor/ にバンドル
- QRCode は esbuild でブラウザ向けにバンドル（npmに build/ なし）
- CDN参照を全てローカル参照に変更、CDNへのネットワークリクエスト完全排除

### Phase 5 Task 32: PWA ✅（2026-04-13）
- manifest.json（name, icons 4種, display: standalone, theme_color）
- Service Worker（全アセット precache, Cache First, 旧キャッシュ自動削除）
- index.html に manifest リンク、theme-color meta、apple-mobile-web-app meta
- beforeinstallprompt ハンドラ（installPWA() API公開）
- テスト 18件追加（manifest/SW/HTML統合）、全パス

### Phase 5 Task 33: ストア準備 ✅（2026-04-13）
- electron-builder.json（Windows NSIS + macOS DMG）
- ビルドスクリプト: build:electron, build:electron:mac, build:android, build:android:bundle
- Android アイコン全密度（mdpi〜xxxhdpi、launcher + round + foreground）
- PWA アイコン 4種（192/512 + maskable）+ SVGマスター
- ストアメタデータ: 説明文（ja/en）、プライバシーポリシー
- テスト 10件追加、全パス

### Phase 5 要件漏れ対応 ✅（2026-04-13）
- ステータスバーの回収済み/返却済みカウント表示
- 操作者管理ダイアログへのUIトリガー（設定パネル内）
- 同一バーコード複数件の選択ダイアログ（ラジオボタン選択式）
- カラムD&D並び替え（ヘッダーのドラッグで列順変更、IndexedDB永続化）
- 横スクロールヒント（テーブル溢れ時の右端フェード）
- 右パネルのトグルボタン（スプリッター上、状態永続化）
- 列ヘッダー×ボタン（ホバーで表示、確認ダイアログ付き）

## テスト
- 全86件パス（i18n 10 + importer 25 + platform 12 + scanner-camera 11 + pwa 18 + store 10）

## ファイル構成（9 JS モジュール）
```
src/js/
  platform.js  25行   プラットフォーム検出
  i18n.js      78行   多言語
  storage.js  119行   IndexedDB
  ui.js       128行   共通UI
  table.js    560行   テーブル（D&D・列削除ボタン追加）
  importer.js 270行   CSV/Excel取込
  printer.js  693行   ラベル印刷
  scanner.js  610行   スキャン + カメラ + 複数件選択
  app.js      270行   初期化（パネルトグル・横スクロールヒント追加）
src/vendor/
  dexie.min.js          IndexedDB
  xlsx.full.min.js      Excel読込
  JsBarcode.all.min.js  バーコード生成
  qrcode.min.js         QRコード生成
  jspdf.umd.min.js      PDF生成
  html5-qrcode.min.js   カメラバーコード読取
```
