; Inno Setup script for the Instagram Eraser.
; Compile with the free Inno Setup compiler (iscc.exe):
;     iscc build\installer.iss
; Produces dist\InstagramEraser-Setup.exe from the PyInstaller onedir build.

#define MyAppName "Instagram Eraser"
#define MyAppVersion "1.0.0"
#define MyAppExeName "InstagramEraser.exe"

[Setup]
AppId={{B7E4B2A1-3C5D-4F6E-9A8B-1C2D3E4F5A6B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\InstagramEraser
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=..\dist
OutputBaseFilename=InstagramEraser-Setup
Compression=lzma2
SolidCompression=yes
; Install per-user so no administrator prompt is required.
PrivilegesRequired=lowest
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
; Bundle the entire PyInstaller onedir output.
Source: "..\dist\InstagramEraser\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
