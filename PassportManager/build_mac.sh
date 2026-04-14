#!/bin/bash
set -e

echo "=========================================="
echo " パスポート管理システム macOS ビルド"
echo "=========================================="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 前回のビルド成果物を削除
rm -rf build dist

# 仮想環境を作成（なければ）
if [ ! -d "venv" ]; then
    echo "[1/4] 仮想環境を作成中..."
    python3 -m venv venv
else
    echo "[1/4] 既存の仮想環境を使用"
fi

# 依存パッケージをインストール
echo "[2/4] 依存パッケージをインストール中..."
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

# PyInstaller でビルド
echo "[3/4] アプリをビルド中..."
pyinstaller passport_manager.spec --noconfirm

echo ""
echo "[4/4] DMG を作成中..."

# DMG 作成
if command -v create-dmg &> /dev/null; then
    # create-dmg が利用可能な場合（brew install create-dmg）
    rm -f dist/PassportManager.dmg
    create-dmg \
        --volname "PassportManager" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "PassportManager.app" 175 190 \
        --hide-extension "PassportManager.app" \
        --app-drop-link 425 190 \
        "dist/PassportManager.dmg" \
        "dist/PassportManager.app" || true
    echo "DMG: dist/PassportManager.dmg"
elif command -v hdiutil &> /dev/null; then
    # macOS 標準の hdiutil を使用
    rm -rf dist/dmg_staging
    mkdir -p dist/dmg_staging
    cp -r dist/PassportManager.app dist/dmg_staging/
    ln -s /Applications dist/dmg_staging/Applications
    rm -f dist/PassportManager.dmg
    hdiutil create -volname "PassportManager" \
        -srcfolder dist/dmg_staging \
        -ov -format UDZO \
        dist/PassportManager.dmg
    rm -rf dist/dmg_staging
    echo "DMG: dist/PassportManager.dmg"
else
    echo "DMG作成ツールがありません。.app をそのまま配布してください。"
fi

echo ""
echo "=========================================="
echo " ビルド完了!"
echo "=========================================="
echo "  アプリ: dist/PassportManager.app"
[ -f dist/PassportManager.dmg ] && echo "  DMG:   dist/PassportManager.dmg"
echo ""
echo "実行方法: open dist/PassportManager.app"
echo "=========================================="
