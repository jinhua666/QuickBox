#ifndef MyAppVersion
  #error MyAppVersion must be supplied by the build script
#endif
[Setup]
AppId={{48F20304-8F38-48FA-99DC-BC652B0B745C}
AppName=QuickBox
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\QuickBox
DefaultGroupName=QuickBox
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=QuickBox-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\QuickBox\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\QuickBox"; Filename: "{app}\QuickBox.exe"
Name: "{autodesktop}\QuickBox"; Filename: "{app}\QuickBox.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\QuickBox.exe"; Description: "Launch QuickBox"; Flags: nowait postinstall skipifsilent
