; Script de Inno Setup para el Sistema Automatizado de Contrataciones.
; El runtime Python y las dependencias viajan en dist\. Ya no se empaqueta
; Chromium de Playwright (la verificación de Alfresco es por API REST).
;
; Compilar:
;   1) powershell -ExecutionPolicy Bypass -File build_gui.ps1
;   2) "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
;
; Resultado: installer_output\Setup_ContratacionesETL_<version>.exe

#define MyAppName "Sistema Automatizado de Contrataciones"
#ifndef MyAppVersion
#define MyAppVersion "1.1.0"
#endif
#define MyAppPublisher "Universidad Industrial de Santander"
#define MyAppExeName "SistemaContrataciones.exe"

[Setup]
AppId={{A7E4F1C2-3B5D-4E6A-9C8F-1D2E3F4A5B6C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\ContratacionesETL
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=installer_output
OutputBaseFilename=Setup_ContratacionesETL_{#MyAppVersion}
SetupIconFile=desktop\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
CloseApplications=yes
RestartApplications=no
MinVersion=10.0

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el Escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked

[Files]
Source: "dist\SistemaContrataciones\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Plantilla de configuración (sin credenciales) para el primer arranque.
Source: ".env.example"; DestDir: "{app}"; DestName: ".env.example"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Iniciar {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\archivos"
Type: filesandordirs; Name: "{app}\logs"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    { Carpetas de trabajo junto al ejecutable (perfil del usuario). }
    ForceDirectories(ExpandConstant('{app}\archivos'));
    ForceDirectories(ExpandConstant('{app}\logs'));
    { Crea .env a partir de la plantilla si el usuario aún no lo tiene. }
    if (not FileExists(ExpandConstant('{app}\.env'))) and
       (FileExists(ExpandConstant('{app}\.env.example'))) then
      FileCopy(ExpandConstant('{app}\.env.example'), ExpandConstant('{app}\.env'), False);
  end;
end;
