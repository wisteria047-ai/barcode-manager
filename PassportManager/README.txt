============================================
 パスポート管理システム (PassportManager)
 v1.0.0
============================================

■ 概要
  クルーズ船旅客のパスポートを管理するデスクトップアプリケーションです。
  CSV取り込み、バーコード生成/印刷、ステータス管理（回収/返却）、
  ラベルシート印刷（PDF出力）に対応しています。

■ 動作環境
  - Python 3.10 以降
  - macOS / Windows / Linux
  - 必須ライブラリ: Pillow

■ ファイル構成
  passport_manager.py   ... メインアプリケーション
  sample_passports.csv  ... サンプルCSVデータ（24項目）
  requirements.txt      ... 依存パッケージ一覧
  passport_manager.spec ... PyInstaller ビルド設定
  build_mac.sh          ... macOS ビルドスクリプト
  build_win.bat         ... Windows ビルドスクリプト
  installer_win.iss     ... Windows インストーラ定義 (Inno Setup)

============================================
 開発モードで実行
============================================

  pip install Pillow
  python passport_manager.py

============================================
 macOS でビルド (.app / .dmg)
============================================

  1. ターミナルでこのフォルダに移動
  2. bash build_mac.sh
  3. dist/PassportManager.app が生成されます
     DMG も自動生成されます（hdiutil使用）

============================================
 Windows でビルド (.exe)
============================================

  1. このフォルダで build_win.bat をダブルクリック
  2. dist\PassportManager.exe が生成されます

  ■ インストーラを作る場合（任意）
    1. Inno Setup をインストール (https://jrsoftware.org/isdl.php)
    2. installer_win.iss を右クリック → Compile
    3. dist\PassportManager_Setup.exe が生成されます

============================================
 データ保存先
============================================

  ■ 開発モード: スクリプトと同じフォルダ
  ■ macOS ビルド版: ~/Library/Application Support/PassportManager/
  ■ Windows ビルド版: %LOCALAPPDATA%\PassportManager\

============================================
 アイコンの設定（任意）
============================================

  macOS: icon.icns をこのフォルダに置くと .app に適用されます
  Windows: icon.ico をこのフォルダに置くと .exe に適用されます

============================================
