# ビルド手順

## 前提条件

- Node.js 18以上
- npm または yarn

## セットアップ

```bash
npm install
```

## デスクトップアプリとして実行（開発モード）

```bash
npm start
```

## Windows EXE をビルド

```bash
# インストーラー付き (NSIS) + ポータブル版
npm run build:win
```

ビルド成果物は `dist/` ディレクトリに出力されます：
- `バーコード管理ツール Setup X.X.X.exe` — インストーラー
- `バーコード管理ツール X.X.X.exe` — ポータブル版（インストール不要）

## macOS をビルド

```bash
npm run build:mac
```

## E2E テスト

```bash
npm test
```
