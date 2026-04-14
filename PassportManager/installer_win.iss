; ==============================================================================
;  installer_win.iss  —  バーコード管理システム v2.0  Inno Setup スクリプト
; ==============================================================================
;  【前提】
;    1. build_win.bat でビルドし dist\BarcodeManager.exe が存在すること
;    2. app.ico が存在すること（create_icon.py で生成）
;    3. Inno Setup 6.x がインストール済みであること
;       https://jrsoftware.org/isdl.php
;
;  【ビルド方法】
;    Inno Setup Compiler を起動し、このファイルを開いて「Compile」を実行する
;    または:  iscc installer_win.iss
;
;  【生成物】
;    dist\BarcodeManager_Setup_v2.0.0.exe  （インストーラー本体）
; ==============================================================================

#define MyAppName      "バーコード管理システム"
#define MyAppNameEn    "BarcodeManager"
#define MyAppVersion   "2.0.0"
#define MyAppPublisher "（販売者名）"                 ; ← 変更してください
#define MyAppURL       "https://example.booth.pm/"  ; ← 販売ページURLに変更
#define MyExeName      "BarcodeManager.exe"
#define MyIconFile     "app.ico"

[Setup]
AppId                    = {{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}  ; ← GUIDを変更
AppName                  = {#MyAppName}
AppVersion               = {#MyAppVersion}
AppVerName               = {#MyAppName} v{#MyAppVersion}
AppPublisher             = {#MyAppPublisher}
AppPublisherURL          = {#MyAppURL}
AppSupportURL            = {#MyAppURL}
AppUpdatesURL            = {#MyAppURL}
DefaultDirName           = {autopf}\{#MyAppNameEn}
DefaultGroupName         = {#MyAppName}
AllowNoIcons             = yes
OutputDir                = dist
OutputBaseFilename       = {#MyAppNameEn}_Setup_v{#MyAppVersion}
SetupIconFile            = {#MyIconFile}
Compression              = lzma2/ultra64
SolidCompression         = yes
WizardStyle              = modern
WizardResizable          = no
PrivilegesRequiredOverridesAllowed = dialog
PrivilegesRequired       = lowest   ; ユーザー権限でインストール可能（管理者不要）
MinVersion               = 6.1      ; Windows 7 以降
ArchitecturesInstallIn64BitMode = x64compatible

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon";  Description: "デスクトップにショートカットを作成(&D)"; \
    GroupDescription: "追加タスク:"; Flags: unchecked

[Files]
; メインの実行ファイル
Source: "dist\{#MyExeName}";   DestDir: "{app}"; Flags: ignoreversion

; アイコンファイル
Source: "{#MyIconFile}";        DestDir: "{app}"; Flags: ignoreversion

; サンプル CSV（初回配布用 — 上書きしない）
Source: "sample_passports.csv"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "sample_books.csv";     DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist

[Icons]
; スタートメニュー
Name: "{group}\{#MyAppName}";       \
    Filename: "{app}\{#MyExeName}"; \
    IconFilename: "{app}\{#MyIconFile}"

Name: "{group}\アンインストール";   \
    Filename: "{uninstallexe}";     \
    IconFilename: "{app}\{#MyIconFile}"

; デスクトップ（タスク選択時のみ）
Name: "{autodesktop}\{#MyAppName}"; \
    Filename: "{app}\{#MyExeName}"; \
    IconFilename: "{app}\{#MyIconFile}"; \
    Tasks: desktopicon

[Run]
; インストール完了後の「アプリを起動する」チェックボックス
Filename: "{app}\{#MyExeName}"; \
    Description: "{cm:LaunchProgram,{#MyAppName}}"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; ※ ユーザーデータは %LOCALAPPDATA%\BarcodeManager\ に保存されるため
;    アンインストールしても消えません（意図的）。
