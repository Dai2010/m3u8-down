#define AppName "m3u8 Downloader"

[Setup]
AppId={{0F5239F7-F0E6-4B8F-A4F9-E0787FB6D5BD}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Dai2010
DefaultDirName={autopf}\m3u8 Downloader
DefaultGroupName=m3u8 Downloader
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=m3u8-downloader-{#AppVersion}-windows-x64
SetupIconFile={#IconFile}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
ChangesEnvironment=yes

[Files]
Source: "{#SourceDir}\m3u8-downloader-gui.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\m3u8-downloader.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\m3u8-downloader-tui.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\m3u8 Downloader GUI"; Filename: "{app}\m3u8-downloader-gui.exe"
Name: "{group}\m3u8 Downloader CLI"; Filename: "{app}\m3u8-downloader.exe"
Name: "{group}\m3u8 Downloader TUI"; Filename: "{app}\m3u8-downloader-tui.exe"
Name: "{autodesktop}\m3u8 Downloader GUI"; Filename: "{app}\m3u8-downloader-gui.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut for the GUI"; GroupDescription: "Additional shortcuts:"

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Check: NeedsAddPath(ExpandConstant('{app}')); Flags: preservestringtype

[Code]
function NeedsAddPath(PathToAdd: string): Boolean;
var
  CurrentPath: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', CurrentPath) then
    CurrentPath := '';
  Result := Pos(';' + Uppercase(PathToAdd) + ';', ';' + Uppercase(CurrentPath) + ';') = 0;
end;
