; Inno Setup 6 – Dictate & Transcription Express Digital (D&TED)
; Dictare și transcriere în limba română
;
; Instalare fără administrator (implicit, doar pentru utilizatorul curent) sau, la
; alegere, pentru toți utilizatorii: {autopf} = %LOCALAPPDATA%\Programs (per utilizator)
; sau Program Files (pentru toți). Programul (dist\DTED, PyInstaller onedir) conține
; Python, PySide6, faster-whisper, ctranslate2, PyAV și ffmpeg. Modelul de transcriere
; (large-v3-turbo-ct2, ~1,6 GB) și bibliotecile CUDA (cuBLAS 12 + cuDNN 9) sunt incluse
; în pachet (kit offline complet) — nu se descarcă nimic la prima pornire.

#define MyAppName "Dictate & Transcription Express Digital (D&TED)"
#define MyAppShortcut "D&TED – Dictate & Transcription Express Digital"
#define MyAppDescription "Dictare și transcriere în limba română"
; AppId-ul rămâne cel vechi (implicit era AppName), ca actualizarea să recunoască instalarea.
#define MyAppIdVechi "Dictare&Transcriere Română"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "D&TED"
#define MyAppExeName "DTED.exe"
#define MyDistDir "..\dist\DTED"

[Setup]
AppId={#MyAppIdVechi}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppComments={#MyAppDescription}
AppPublisher={#MyAppPublisher}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={autopf}\D&TED – Dictare și transcriere în limba română
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
OutputDir=..\output
OutputBaseFilename=Setup DTED
; Pictograma fara cadrul de 512 px (ISCC refuza resursa prea mare: "File is too large").
SetupIconFile=iconita_setup.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ShowLanguageDialog=auto

[Languages]
Name: "romanian"; MessagesFile: "Romanian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
romanian.FinishedLabel=Programul a fost instalat. Modelul de transcriere și bibliotecile necesare sunt incluse în pachet, deci nu este nevoie de internet la prima pornire.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\{#MyAppShortcut}"; Filename: "{app}\{#MyAppExeName}"; Comment: "{#MyAppDescription}"; Tasks: desktopicon
Name: "{autoprograms}\{#MyAppShortcut}"; Filename: "{app}\{#MyAppExeName}"; Comment: "{#MyAppDescription}"
Name: "{autoprograms}\D&TED – Dezinstalare"; Filename: "{uninstallexe}"; Comment: "Scoate {#MyAppName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
