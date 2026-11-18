#define AppName "Nubetalo Admin Downloader"
#define AppVersion "0.3.0"
[Setup]
AppId={{A6CA77C2-47DC-43AC-9A26-26B0D18C055C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Nubetalo
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName=Nubetalo
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
UninstallDisplayIcon={app}\{#AppName}.exe
OutputDir=output
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
SetupIconFile=..\assets\app.ico
LicenseFile=..\LICENSE.txt
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio / Create desktop shortcut"
Name: "torrentassoc"; Description: "Asociar archivos .torrent / Associate .torrent files"; Flags: unchecked
Name: "magnetassoc"; Description: "Ofrecer Nubetalo para enlaces magnet en Aplicaciones predeterminadas / Register as an option for magnet links"; Flags: unchecked

[Files]
Source: "..\dist\{#AppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"
Source: "..\PRIVACY.md"; DestDir: "{app}"
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"
Source: "..\LICENSE.txt"; DestDir: "{app}"
Source: "..\LEGAL.md"; DestDir: "{app}"
Source: "..\SECURITY.md"; DestDir: "{app}"
Source: "..\BUILD.md"; DestDir: "{app}"
Source: "..\COPYRIGHT.md"; DestDir: "{app}"
Source: "..\build\legal-licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\Nubetalo Admin Downloader-Source-0.3.0.zip"; DestDir: "{app}"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppName}.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppName}.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Classes\NubetaloDownloader.torrent"; ValueType: string; ValueData: "BitTorrent"; Flags: uninsdeletekey; Tasks: torrentassoc
Root: HKCU; Subkey: "Software\Classes\NubetaloDownloader.torrent\DefaultIcon"; ValueType: string; ValueData: "{app}\{#AppName}.exe,0"; Tasks: torrentassoc
Root: HKCU; Subkey: "Software\Classes\NubetaloDownloader.torrent\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppName}.exe"" ""%1"""; Tasks: torrentassoc
Root: HKCU; Subkey: "Software\Classes\.torrent\OpenWithProgids"; ValueName: "NubetaloDownloader.torrent"; ValueType: none; Flags: uninsdeletevalue; Tasks: torrentassoc
Root: HKCU; Subkey: "Software\Classes\NubetaloDownloader.magnet"; ValueType: string; ValueData: "URL:Nubetalo magnet"; Flags: uninsdeletekey; Tasks: magnetassoc
Root: HKCU; Subkey: "Software\Classes\NubetaloDownloader.magnet"; ValueName: "URL Protocol"; ValueType: string; ValueData: ""; Tasks: magnetassoc
Root: HKCU; Subkey: "Software\Classes\NubetaloDownloader.magnet\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppName}.exe"" ""%1"""; Tasks: magnetassoc
Root: HKCU; Subkey: "Software\Nubetalo\Downloader\Capabilities"; ValueName: "ApplicationName"; ValueType: string; ValueData: "{#AppName}"; Flags: uninsdeletekey; Tasks: torrentassoc or magnetassoc
Root: HKCU; Subkey: "Software\Nubetalo\Downloader\Capabilities\FileAssociations"; ValueName: ".torrent"; ValueType: string; ValueData: "NubetaloDownloader.torrent"; Tasks: torrentassoc
Root: HKCU; Subkey: "Software\Nubetalo\Downloader\Capabilities\UrlAssociations"; ValueName: "magnet"; ValueType: string; ValueData: "NubetaloDownloader.magnet"; Tasks: magnetassoc
Root: HKCU; Subkey: "Software\RegisteredApplications"; ValueName: "{#AppName}"; ValueType: string; ValueData: "Software\Nubetalo\Downloader\Capabilities"; Flags: uninsdeletevalue; Tasks: torrentassoc or magnetassoc

[Run]
Filename: "{app}\{#AppName}.exe"; Description: "Abrir / Open {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\*.log"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ExistingCommand: String;
begin
  if CurUninstallStep = usUninstall then begin
    if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', '{#AppName}', ExistingCommand) then begin
      if CompareText(ExistingCommand, ExpandConstant('"{app}\{#AppName}.exe" --background')) = 0 then
        RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', '{#AppName}');
    end;
  end;
end;
