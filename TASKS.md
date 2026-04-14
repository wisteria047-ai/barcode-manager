# タスクリスト — バーコード管理ツール v3.0

## Phase 1: 基盤 + データ管理 ✅

- [x] Task 0: プロジェクト初期化（Electron + Vanilla JS + Dexie.js）
- [x] Task 1: 1画面レイアウト（ツールバー/フィルター/テーブル/スキャンパネル/ステータスバー）
- [x] Task 2: i18n（日本語/英語、data-i18n属性、設定から切替）
- [x] Task 3: IndexedDB ストレージ（items/settings/columns/history）
- [x] Task 4: 空状態UI + サンプルデータ12件
- [x] Task 5: CSV/Excel取込（D&D + ファイルダイアログ、文字化け自動検知）
- [x] Task 6: テーブル表示 + ページネーション（20/50/100件切替）
- [x] Task 7: インライン編集（行単位の編集/保存/取消）
- [x] Task 8: 行追加（末尾に空行→即編集モード）
- [x] Task 9: カラム管理（追加/削除/名前変更/リサイズ、上限30列）
- [x] Task 10: 検索 + ソート（インクリメンタル検索、列ヘッダーソート）
- [x] Task 11: テンプレートDL + CSVエクスポート（BOM付きUTF-8）
- [x] Task 12: 設定永続化（言語/フォントサイズ/パネル幅/カラム幅）

## Phase 2: バーコード + ラベル印刷 ✅

- [x] Task 13: バーコード生成（JsBarcode Code128/Code39 + QRCode）
- [x] Task 14: バーコード設定UI（列選択、形式、テキスト表示トグル）
- [x] Task 15: ラベルレイアウト設定（用紙プリセット A4各種、余白、ラベルサイズ、配列、間隔、開始位置）
- [x] Task 16: ラベル内容カスタマイズ（列ごとにバーコード/テキスト/ラベル付テキスト/非表示 + 一括操作）
- [x] Task 17: 印刷プレビュー + PDF出力（Canvasリアルタイムプレビュー、ページ送り、jsPDF）
- [x] Task 18: 印刷プリセット保存（設定自動保存 + ユーザー名前付きプリセット）

## Phase 3: スキャン + 貸出/返却 ✅

- [x] Task 19: スキャンパネルUI（入力フィールド、モード切替、操作履歴）
- [x] Task 20: 即時反映モード（スキャン→在庫あり:貸出フォーム / 貸出中:即返却）
- [x] Task 21: 一括モード（スキャン溜め込み→適用で一括処理）
- [x] Task 22: 貸出・返却フロー（貸出先プリセット選択、返却予定日、自動ステータス変更）
- [x] Task 23: 貸出状況一覧（ステータスバッジ 在庫あり/貸出中/延滞 + ステータスフィルター）
- [x] Task 24: 操作者管理（自動登録 + 管理ダイアログ）

---

## Phase 4: 振り返り + リファクタリング 🔄

Phase 1〜3 の実装を振り返り、品質・UX・保守性を改善する。

### コード品質

- [x] **Task 25: コードレビュー + リファクタリング**
  - ~~table.js が大きい（400行超）~~ → 510行。分割は Phase 5 でバンドラー導入時に実施
  - ~~escapeHtml が table.js に直書き~~ → UI.escapeHtml に委譲
  - ~~showToast, showConfirm, showUndo が app.js にグローバル~~ → ui.js に集約（後方互換維持）
  - 循環参照なし確認済み

- [x] **Task 26: エラーハンドリング見直し**
  - **SheetJS 読込バグ修正**: index.html に xlsx スクリプトタグ追加（Excel取込が壊れていた）
  - CDN読込チェック: オフライン時にエラーバナー表示
  - ~~大量データ・IndexedDB容量・バーコード複数件~~ → Phase 5 送り

### UX改善

- [x] **Task 27: UI品質チェック**
  - モーダルのフォーカストラップ追加（Tab循環）
  - 確認ダイアログ: キャンセルに初期フォーカス（破壊的操作の安全デフォルト）
  - トースト重複排除（100ms デバウンス）
  - Cmd+Z ショートカット（Undoバー表示中にトリガー）
  - ~~ダークモード目視確認~~ → Electron 実行時に確認

- [x] **Task 28: アクセシビリティ**
  - 全モーダルに role="dialog" aria-modal="true" aria-labelledby
  - テーブルに caption, scope="col"、全選択チェックに aria-label
  - 閉じる/選択解除ボタンに aria-label
  - Undoバーに role="status" aria-live="polite"
  - .sr-only CSS クラス追加
  - prefers-reduced-motion 適用済み確認

### 機能補完

- [x] **Task 29: 未実装の要件漏れ確認**
  - 要件定義との突き合わせ完了。未実装リストは STATUS.md に記録
  - ステータスフィルター: _status フィールドで正しくフィルターされる（table.js:85）
  - 未対応: カラムD&D、横スクロールヒント、右パネルトグル、列×ボタン等

- [x] **Task 30: テスト追加**
  - vitest + jsdom 環境で 35 テスト（全パス）
  - i18n.test.js: t() キー解決、パラメータ置換、欠落キー（10テスト）
  - importer.test.js: CSV パース RFC 4180、文字化け検出、エスケープ（25テスト）
  - ~~storage.js, scanner.js~~ → IndexedDB モックが必要、Phase 5 で追加

---

## Phase 5: マルチプラットフォーム ✅

- [x] **Task 31: Android（Capacitor + カメラスキャン）**
  - Capacitor v8 セットアップ（core + cli + android）
  - capacitor.config.json（appId: com.barcode.manager）
  - html5-qrcode をローカル配置（src/vendor/、Web API ベースでオフライン対応）
  - platform.js 新規（Capacitor/Electron/Web 検出、カメラAPI有無）
  - scanner.js 拡張（カメラスキャン start/stop/pause-resume、振動フィードバック）
  - カメラスキャンモーダル UI + モバイルレスポンシブ CSS
  - AndroidManifest.xml にカメラ権限追加
  - i18n キー追加（ja/en 各7キー）
  - テスト 23件追加（platform 12 + scanner-camera 11）、全58件パス

- [x] **CDN → ローカルバンドル化**
  - 5ライブラリ（Dexie, SheetJS, JsBarcode, QRCode, jsPDF）を src/vendor/ にバンドル
  - QRCode は esbuild でブラウザビルド（npm に build/ なし）
  - index.html の CDN script タグを全てローカル参照に変更

- [x] **Task 32: PWA（Service Worker + オフライン対応）**
  - manifest.json（icons 4種、display: standalone、theme_color）
  - Service Worker（全アセット precache、Cache First、旧キャッシュ自動削除）
  - index.html に manifest/theme-color/apple-mobile-web-app meta 追加
  - beforeinstallprompt ハンドラ
  - テスト 18件追加、全パス

- [x] **Task 33: ストア準備（アイコン・ビルドスクリプト・メタデータ）**
  - electron-builder.json（Windows NSIS + macOS DMG）
  - ビルドスクリプト: build:electron, build:android, build:android:bundle
  - Android アイコン全密度（mdpi〜xxxhdpi）
  - PWA アイコン 4種 + SVGマスター
  - ストアメタデータ: 説明文（ja/en）、プライバシーポリシー
  - テスト 10件追加、全パス

- [x] **要件漏れ対応（7項目）**
  - ステータスバーの回収済み/返却済みカウント表示
  - 操作者管理ダイアログへのUIトリガー（設定パネル内ボタン）
  - 同一バーコード複数件の選択ダイアログ
  - カラムD&D並び替え（ヘッダードラッグ、IndexedDB永続化）
  - 横スクロールヒント（テーブル溢れ時フェード）
  - 右パネルのトグルボタン（スプリッター上、状態永続化）
  - 列ヘッダー×ボタン（ホバー表示、確認ダイアログ付き）
