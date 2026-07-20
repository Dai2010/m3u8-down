#define AppName "m3u8 Downloader"
#ifndef AppVersion
#define AppVersion "5.0.0"
#endif
#ifndef DisplayVersion
#define DisplayVersion AppVersion
#endif
#ifndef AssetVersion
#define AssetVersion DisplayVersion
#endif
#ifndef LicenseFile
#define LicenseFile "..\..\LICENSE"
#endif

[Setup]
AppId={{0F5239F7-F0E6-4B8F-A4F9-E0787FB6D5BD}
AppName={#AppName}
AppVersion={#DisplayVersion}
AppVerName={#AppName} {#DisplayVersion}
AppPublisher=Dai2010
AppPublisherURL=https://github.com/Dai2010
AppSupportURL=https://github.com/Dai2010/m3u8-down
AppUpdatesURL=https://github.com/Dai2010/m3u8-down/releases
DefaultDirName={autopf}\m3u8 Downloader
DefaultGroupName=m3u8 Downloader
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=m3u8-downloader-{#AssetVersion}-windows-x64
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\m3u8-downloader.ico
LicenseFile={#LicenseFile}
VersionInfoVersion={#AppVersion}
VersionInfoCompany=Dai2010
VersionInfoDescription=m3u8 Downloader Windows installer - GPL License v3.0
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
ChangesEnvironment=yes

[Files]
Source: "{#SourceDir}\m3u8-downloader-gui.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\m3u8-downloader.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\m3u8-downloader-tui.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#IconFile}"; DestDir: "{app}"; DestName: "m3u8-downloader.ico"; Flags: ignoreversion

[Icons]
Name: "{group}\m3u8 Downloader GUI"; Filename: "{app}\m3u8-downloader-gui.exe"; IconFilename: "{app}\m3u8-downloader.ico"
Name: "{group}\m3u8 Downloader CLI"; Filename: "{app}\m3u8-downloader.exe"; IconFilename: "{app}\m3u8-downloader.ico"
Name: "{group}\m3u8 Downloader TUI"; Filename: "{app}\m3u8-downloader-tui.exe"; IconFilename: "{app}\m3u8-downloader.ico"
Name: "{autodesktop}\m3u8 Downloader GUI"; Filename: "{app}\m3u8-downloader-gui.exe"; IconFilename: "{app}\m3u8-downloader.ico"; Tasks: desktopicon

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
