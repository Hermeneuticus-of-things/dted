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
#define MyAppVersion "0.6.2"
#define MyAppPublisher "D&TED"
#define MyAppExeName "DTED.exe"
#define MyDistDir "..\dist-v0.6.2\DTED"
; Iconița programului (microfon auriu, unde care vin spre microfon, litere argintii).
; Se copiază separat lângă program, ca scurtăturile să o arate chiar dacă DTED.exe
; a fost construit cu o iconiță mai veche.
#define MyAppIconName "iconita_dted_text.ico"
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
OutputDir=..\output-v0.6.2
OutputBaseFilename=Setup.DTED-0.6.2
; Pictograma fără cadrul de 512 px (ISCC refuză resursa prea mare: „File is too large”).
; Iconița nouă a instalatorului (aceeași imagine ca a programului, fără cadrul de 512 px).
SetupIconFile=iconita_setup_text.ico
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

[Code]
type
  TMemoryStatusEx = record
    dwLength: DWORD;
    dwMemoryLoad: DWORD;
    ullTotalPhys: Int64;
    ullAvailPhys: Int64;
    ullTotalPageFile: Int64;
    ullAvailPageFile: Int64;
    ullTotalVirtual: Int64;
    ullAvailVirtual: Int64;
    ullAvailExtendedVirtual: Int64;
  end;

function GlobalMemoryStatusEx(var lpBuffer: TMemoryStatusEx): BOOL;
  external 'GlobalMemoryStatusEx@kernel32.dll stdcall';

var
  HardwarePage: TOutputMsgMemoWizardPage;

function MemorieTotalaGB: Integer;
var
  Mem: TMemoryStatusEx;
begin
  Result := 0;
  Mem.dwLength := SizeOf(Mem);
  if GlobalMemoryStatusEx(Mem) then
    Result := Round(Mem.ullTotalPhys / (1024.0 * 1024.0 * 1024.0));
end;

function ArePlacaNvidia(var NumeAdaptor: String): Boolean;
var
  CheieClasa, SubCheie, Adaptor: String;
  Index: Integer;
begin
  Result := False;
  NumeAdaptor := '';
  CheieClasa := 'SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}';
  for Index := 0 to 15 do
  begin
    SubCheie := CheieClasa + '\' + Format('%.4d', [Index]);
    if RegQueryStringValue(HKLM, SubCheie, 'DriverDesc', Adaptor) then
    begin
      if Pos('NVIDIA', Uppercase(Adaptor)) > 0 then
      begin
        Result := True;
        NumeAdaptor := Adaptor;
        Exit;
      end;
    end;
  end;
end;

function VersiuneVecheInstalata(var VersiuneVeche, UninstallCmd: String): Boolean;
var
  Cheie: String;
begin
  Result := False;
  VersiuneVeche := '';
  UninstallCmd := '';
  Cheie := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppIdVechi}_is1';
  if RegQueryStringValue(HKCU, Cheie, 'DisplayVersion', VersiuneVeche) then
  begin
    RegQueryStringValue(HKCU, Cheie, 'UninstallString', UninstallCmd);
    Result := True;
  end
  else if RegQueryStringValue(HKLM, Cheie, 'DisplayVersion', VersiuneVeche) then
  begin
    RegQueryStringValue(HKLM, Cheie, 'UninstallString', UninstallCmd);
    Result := True;
  end;
end;

procedure CurataConflicteVechi;
var
  VersVeche, CmdVeche: String;
  CodRezultat: Integer;
begin
  // Șterge scurtături vechi cu denumirea anterioară, ca să nu rămână dubluri.
  DeleteFile(ExpandConstant('{autodesktop}\Dictare și transcriere în limba română.lnk'));
  DeleteFile(ExpandConstant('{autoprograms}\Dictare și transcriere în limba română.lnk'));
  if VersiuneVecheInstalata(VersVeche, CmdVeche) then
  begin
    if (VersVeche <> '{#MyAppVersion}') and (CmdVeche <> '') then
    begin
      CmdVeche := RemoveQuotes(CmdVeche);
      if FileExists(CmdVeche) then
        Exec(CmdVeche, '/VERYSILENT /NORESTART /SUPPRESSMSGBOXES', '', SW_HIDE, ewWaitUntilTerminated, CodRezultat);
    end;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  CurataConflicteVechi;
end;

procedure InitializeWizard;
var
  LiberMB, TotalMB: Cardinal;
  LiberGB, RamGB: Integer;
  NumeGPU, VersVeche, CmdVeche, Raport: String;
  AreGPU, AreVeche: Boolean;
begin
  HardwarePage := CreateOutputMsgMemoPage(
    wpWelcome,
    'Verificare calculator și instalări anterioare',
    'Verificăm resursele calculatorului pentru transcriere în limba română.',
    'Rezultatul verificării automate (instalarea poate continua pe orice calculator):',
    ''
  );

  LiberGB := 0;
  if GetSpaceOnDisk(ExpandConstant('{autopf}'), True, LiberMB, TotalMB) then
    LiberGB := LiberMB div 1024;
  RamGB := MemorieTotalaGB;

  AreGPU := ArePlacaNvidia(NumeGPU);
  AreVeche := VersiuneVecheInstalata(VersVeche, CmdVeche);

  Raport := '• Sistem de operare: Windows ' + GetWindowsVersionString + #13#10;
  Raport := Raport + '• Procesor (CPU): ' + GetEnv('NUMBER_OF_PROCESSORS') + ' fire de execuție' + #13#10;
  Raport := Raport + '• Memorie RAM: ' + IntToStr(RamGB) + ' GB (minim 8 GB, recomandat 16 GB)' + #13#10;
  Raport := Raport + '• Spațiu liber pe disc: ' + IntToStr(LiberGB) + ' GB (minim 6 GB necesari)' + #13#10;
  if AreGPU then
    Raport := Raport + '• Placă video (GPU): ' + NumeGPU + ' (transcriere rapidă pe GPU cu CUDA inclus)' + #13#10
  else
    Raport := Raport + '• Placă video (GPU): fără GPU NVIDIA dedicat — programul va folosi procesorul (CPU float32)' + #13#10;

  if AreVeche then
    Raport := Raport + #13#10 + '• Versiune anterioară găsită (' + VersVeche + '): conflictele vechi vor fi eliminate automat înainte de instalarea versiunii {#MyAppVersion}, păstrând toate documentele și setările.'
  else
    Raport := Raport + #13#10 + '• Instalare curată: nu există conflicte cu versiuni anterioare.';

  HardwarePage.RichEditViewer.Lines.Text := Raport;
end;
