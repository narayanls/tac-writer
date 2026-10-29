#define MyAppName "Tac Writer"
#define MyAppVersion "1.5.0-1"
#define MyAppNumericVersion "1.5.0.1"
#define MyAppPublisher "TAC"
#define MyAppURL "https://github.com/narayanls/tac-writer"
#define MyAppExeName "TacWriter.exe"

[Setup]
AppId={{F7A3B2C1-94D6-4E5F-B8A7-1C2D3E4F5A6B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\TacWriter
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=TacWriter-{#MyAppVersion}-Setup-x64
SetupIconFile=icons\hicolor\scalable\apps\tac-writer.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
VersionInfoVersion={#MyAppNumericVersion}
VersionInfoProductVersion={#MyAppNumericVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoProductName={#MyAppName}
DisableWelcomePage=no
InfoBeforeFile=INFO_BEFORE.txt

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "quicklaunchicon"; Description: "Fixar na barra de tarefas"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\TacWriter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "Editor de texto para escritores"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName} agora"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Registry]
Root: HKLM; Subkey: "Software\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  VersionPath: String;
  AppDataFolder: String;
begin
  if CurStep = ssPostInstall then
  begin
    // Define os caminhos
    AppDataFolder := ExpandConstant('{localappdata}\tac');
    VersionPath := AddBackslash(AppDataFolder) + 'version.txt';

    // CORREÇÃO: Cria a pasta 'tac' se ela não existir, senão o SaveStringToFile falha
    if not DirExists(AppDataFolder) then
      ForceDirectories(AppDataFolder);

    // Salva a versão (sobrescreve se existir)
    SaveStringToFile(VersionPath, '{#MyAppVersion}', True);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
DelTree(ExpandConstant('{localappdata}\tac\version.txt'), True, True, True);
  end;
