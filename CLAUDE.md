# バーコード管理ツール v3.0

## プロジェクト概要

2つの既存アプリ（Python版 passport-manager + Electron版 barcode-module）を統合し、
マルチプラットフォーム販売可能な物品管理ツールを構築する。

- **UIモデル**: Python版の1画面構成（テーブル主役 + スキャン常駐右パネル）
- **技術基盤**: Electron + Capacitor + PWA（Vanilla JS）
- **対象ユーザー**: 事務員・現場作業員（ITリテラシー低め）
- **プラットフォーム**: Windows PC（メイン）+ Android（棚卸し用）+ PWA

## 開発ルール

### 基本方針
- ユーザーはエンジニアではない。技術的な質問や確認は最小限にすること
- 判断に迷ったら、シンプルな方を選ぶこと
- 1つの機能を実装したら、動作確認できる状態にしてから次に進むこと
- エラーメッセージは日本語で、ユーザーにわかる言葉で書くこと
- テストを先に書いてから実装する（テスト駆動）
- **元の2つのアプリのファイルは一切変更しない**

### 参照ファイル
- 要件定義: `/Volumes/開発環境１/projects/stable/barcode-module/requirements-v3.md`
- Python版（UI参考）: `/Volumes/開発環境１/projects/stable/passport-manager/`
- Electron版（機能参考）: `/Volumes/開発環境１/projects/stable/barcode-module/`

### 技術スタック

| レイヤー | 技術 | 用途 |
|----------|------|------|
| フロントエンド | HTML + CSS + Vanilla JS | UI全般 |
| デスクトップ | Electron | Windows配布 |
| モバイル | Capacitor | Android配布 |
| PWA | Service Worker + manifest.json | Web配布 |
| データ保存 | IndexedDB（Dexie.js） | オフライン永続化 |
| i18n | locales/ja.json + en.json + t() 関数 | 多言語 |
| バーコード生成 | JsBarcode + qrcode.js | Code128/Code39/QR |
| PDF生成 | jsPDF | ラベル印刷 |
| Excel読込 | SheetJS (xlsx) | CSV/Excel取込 |

### フォルダ構造

```
barcode-manager/
├── CLAUDE.md
├── TASKS.md
├── package.json
├── electron/
│   ├── main.js           # Electronメインプロセス
│   └── preload.js        # プリロードスクリプト
├── src/
│   ├── index.html         # 1画面レイアウト
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   ├── app.js         # 初期化・イベントバインド
│   │   ├── table.js       # テーブル表示・編集・ソート
│   │   ├── scanner.js     # スキャンパネル・即時/一括モード
│   │   ├── printer.js     # ラベル印刷・PDF生成
│   │   ├── importer.js    # CSV/Excel取込・文字化け対策
│   │   ├── storage.js     # IndexedDB永続化（Dexie.js）
│   │   ├── i18n.js        # 多言語切替
│   │   ├── lending.js     # 貸出・返却管理
│   │   ├── history.js     # 操作履歴・Undo
│   │   └── settings.js    # 設定管理・レイアウト保存
│   ├── locales/
│   │   ├── ja.json
│   │   └── en.json
│   └── assets/
│       └── icons/
├── tests/                  # テストファイル
├── capacitor.config.json
└── sw.js                   # Service Worker
```

## 画面構成（1画面・タブなし）

```
┌──────────────────────────────────────────────────────┐
│ ツールバー                                            │
├──────────────────────────────────┬───────────────────┤
│ フィルターバー                    │ スキャンパネル     │
│ テーブル（画面の70%以上）          │ バーコードプレビュー │
│                                  │ 操作履歴           │
├──────────────────────────────────┴───────────────────┤
│ ステータスバー                                        │
└──────────────────────────────────────────────────────┘
```

- **テーブルが主役**: デフォルトで画面の70%以上
- **スキャン常駐**: 右パネルは常時表示（折りたたみ可能）
- **タブ不要**: 全機能が1画面でアクセス可能

## Phase 構成

| Phase | 範囲 | 完了条件 |
|-------|------|----------|
| **Phase 1** | **基盤 + データ管理** | テーブル表示・編集・CSV取込が動く |
| Phase 2 | バーコード + ラベル印刷 | ラベルPDFを出力できる |
| Phase 3 | スキャン + 貸出/返却 | スキャン運用ができる |
| Phase 4 | カスタマイズ + 仕上げ | レイアウト調整・Undo・ダークモード |
| Phase 5 | マルチプラットフォーム | Android + PWA |

## 現在の Phase: Phase 1（基盤 + データ管理）

Phase 1 の完了条件:
- Electronアプリが起動し、1画面レイアウトが表示される
- CSV/Excelファイルをドラッグ&ドロップで取り込める
- テーブルでデータの表示・インライン編集・追加・削除ができる
- 検索・ソートが動作する
- カラムの追加・削除・名前変更・並び替えができる
- データがIndexedDBに永続化される
- 日本語/英語の切替ができる
- サンプルデータで即座にデモ体験できる
