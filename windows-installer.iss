[Setup]
AppId={{DFD0F246-2E7E-4B8C-945E-D450A8126F09}
AppName=StudyDesk
AppVersion=0.2.0
AppPublisher=StudyDesk contributors
AppPublisherURL=https://github.com/UIBE-guan-dan/studydesk
DefaultDirName={localappdata}\Programs\StudyDesk
DefaultGroupName=StudyDesk
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=output\windows\release
OutputBaseFilename=StudyDesk-0.2.0-windows-x64-setup
SetupIconFile=study.ico
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\StudyDesk.exe
CloseApplications=no

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "output\windows\dist\StudyDesk\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\StudyDesk"; Filename: "{app}\StudyDesk.exe"
Name: "{userdesktop}\StudyDesk"; Filename: "{app}\StudyDesk.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\StudyDesk.exe"; Description: "Launch StudyDesk"; Flags: nowait postinstall skipifsilent
