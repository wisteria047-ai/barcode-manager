@echo off
chcp 65001 >nul
echo ==========================================
echo  バーコード管理システム v2.0  Windows ビルド
echo ==========================================
echo.

cd /d "%~dp0"

REM ── 前回ビルドを削除 ──────────────────────────────────────
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

REM ── 仮想環境 ────────────────────────────────────────────────
if not exist venv (
    echo [1/5] 仮想環境を作成中...
    python -m venv venv
) else (
    echo [1/5] 既存の仮想環境を使用
)

echo [2/5] 依存パッケージをインストール中...
call venv\Scripts\activate.bat
pip install --upgrade pip -q
pip install -r requirements.txt -q

REM ── アイコン生成 ─────────────────────────────────────────────
echo [3/5] アイコンを生成中...
python create_icon.py
if not exist app.ico (
    echo [警告] app.ico の生成に失敗しました。アイコンなしでビルドを続行します。
    set ICON_OPT=
) else (
    set ICON_OPT=--icon app.ico
)

REM ── PyInstaller ──────────────────────────────────────────────
echo [4/5] アプリをビルド中...
pyinstaller --noconfirm --onefile --windowed ^
    --name "BarcodeManager" ^
    %ICON_OPT% ^
    --add-data "sample_passports.csv;." ^
    --add-data "sample_books.csv;." ^
    manager_app.py

if not exist dist\BarcodeManager.exe (
    echo [エラー] EXE の生成に失敗しました。
    pause
    exit /b 1
)

REM ── Inno Setup インストーラー ────────────────────────────────
echo [5/5] インストーラーを作成中...

REM Inno Setup のインストール場所を自動検索
set ISCC=
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
) else if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set ISCC="%ProgramFiles%\Inno Setup 6\ISCC.exe"
) else if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)

if defined ISCC (
    %ISCC% installer_win.iss
    if exist dist\BarcodeManager_Setup_v2.0.0.exe (
        echo.
        echo ==========================================
        echo  ビルド完了！
        echo ==========================================
        echo   EXE:        dist\BarcodeManager.exe
        echo   インストーラー: dist\BarcodeManager_Setup_v2.0.0.exe
        echo.
        echo Booth にアップロードするファイル:
        echo   dist\BarcodeManager_Setup_v2.0.0.exe
        echo ==========================================
    ) else (
        echo [警告] インストーラーの生成に失敗しました。
        echo        EXE のみ使用できます: dist\BarcodeManager.exe
    )
) else (
    echo.
    echo ==========================================
    echo  EXE ビルド完了！
    echo ==========================================
    echo   EXE: dist\BarcodeManager.exe
    echo.
    echo [情報] Inno Setup が見つかりませんでした。
    echo        インストーラーを作成するには:
    echo        https://jrsoftware.org/isdl.php
    echo        をインストールして再実行してください。
    echo ==========================================
)

echo.
pause
