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
#define MyAppVersion "0.1.0"
#define MyAppPublisher "D&TED"
#define MyAppExeName "DTED.exe"
#define MyDistDir "..\dist\DTED"
; Iconița programului (microfon auriu, unde care vin spre microfon).
; Se copiază separat lângă program, ca scurtăturile să o arate chiar dacă DTED.exe
; a fost construit cu o iconiță mai veche.
#define MyAppIconName "iconita_dictare.ico"
; Același identificator e setat și în program (ui_qt\principal.py), ca bara de activități
; să grupeze fereastra cu scurtătura și să arate iconița programului.
#define MyAppUserModelID "DTED.DictareTranscriere"

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
UninstallDisplayIcon={app}\{#MyAppIconName}
UninstallDisplayName={#MyAppName}
OutputDir=..\output
OutputBaseFilename=Setup DTED
; Pictograma fără cadrul de 512 px (ISCC refuză resursa prea mare: „File is too large”).
; Iconița nouă a instalatorului (aceeași imagine ca a programului, fără cadrul de 512 px).
SetupIconFile=iconita_setup.ico
Compression=lzma2
SolidCompression=yes
; GitHub limitează fișierele la 2 GB ⇒ instalatorul se împarte în bucăți < 2 GB.
; ISCC produce "Setup DTED.exe" + "Setup DTED-1.bin", "Setup DTED-2.bin", ... —
; toate trebuie să stea în același folder la instalare (exe-ul le citește singur).
DiskSpanning=yes
DiskSliceSize=2000000000
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
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dictare_transcriere_romana\{#MyAppIconName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autodesktop}\{#MyAppShortcut}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppIconName}"; AppUserModelID: "{#MyAppUserModelID}"; Comment: "{#MyAppDescription}"; Tasks: desktopicon
Name: "{autoprograms}\{#MyAppShortcut}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppIconName}"; AppUserModelID: "{#MyAppUserModelID}"; Comment: "{#MyAppDescription}"
Name: "{autoprograms}\D&TED – Dezinstalare"; Filename: "{uninstallexe}"; Comment: "Scoate {#MyAppName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
