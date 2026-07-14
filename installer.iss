; ============================================================================
;  Inno Setup script for the PingSentry Windows installer.
;
;  Prerequisites:
;    1. Build the executable first:      build.bat   (runs PyInstaller)
;       -> produces dist\PingSentry.exe
;    2. Install Inno Setup:              https://jrsoftware.org/isdl.php
;
;  Compile:
;    iscc installer.iss
;       -> produces dist\PingSentry-Setup.exe
;
;  The resulting Setup.exe installs PingSentry into Program Files, creates
;  Start-menu and (optional) desktop shortcuts, and offers to launch the app
;  at Windows startup so monitoring resumes automatically.
; ============================================================================

#define MyAppName "PingSentry"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "PingSentry"
#define MyAppExeName "PingSentry.exe"

[Setup]
AppId={{7B1F3C2A-9D64-4E7B-9C1E-PINGSENTRY001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=PingSentry-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
; Per-user install (no admin required). Use "admin" for machine-wide.
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"
Name: "startupicon"; Description: "Start {#MyAppName} automatically when Windows starts"; GroupDescription: "Startup:"

[Files]
; The single-file EXE produced by PyInstaller already bundles on.wav/off.wav.
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName} now"; Flags: nowait postinstall skipifsilent
