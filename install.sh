#!/usr/bin/env bash
# Dictate & Transcription Express Digital (D&TED) – Dictare și transcriere în limba română
# Instalare automată pe Linux (x86_64), fără drepturi de administrator pentru program.
# Pune: mediu Python propriu (faster-whisper, ctranslate2, PyAV, PySide6, ffmpeg inclus),
# programul, o scurtătură în meniu, apoi descarcă modelul (cu SHA-256) și, doar dacă
# există placă NVIDIA, bibliotecile CUDA (cuBLAS 12, cuDNN 9) în folderul de date.
# PyTorch NU este instalat (motorul folosește CTranslate2).
#
# SOLID (bug 0.6.11): dacă fișierul a ajuns cu terminatoare de linie Windows
# (CRLF — de exemplu dintr-un kit construit pe Windows), se auto-corectează
# într-o copie temporară și continuă, în loc să eșueze la „set -o pipefail”.
if ! tr -d '\r' < "$0" | cmp -s - "$0"; then t="$(mktemp "${TMPDIR:-/tmp}/dted-install.XXXXXX.sh")"; tr -d '\r' < "$0" > "$t"; export DTED_SURSA="$(cd "$(dirname "$0")" && pwd)"; exec bash "$t" "$@"; fi # copie curată LF; tot rândul e pe o singură linie terminată în comentariu, ca să tolereze \r peste tot
set -euo pipefail

SURSA="${DTED_SURSA:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
DATE="${DTED_DATE:-${XDG_DATA_HOME:-$HOME/.local/share}/dted}"
APP="$DATE/program"
MEDIU="$DATE/mediu"
LANSATOR="$HOME/.local/bin/dted"
MENIU="${XDG_DATA_HOME:-$HOME/.local/share}/applications/dted.desktop"

spune() { printf '\n==> %s\n' "$*"; }
eroare() { printf '\nEROARE: %s\n' "$*" >&2; exit 1; }

[ "$(uname -m)" = "x86_64" ] || eroare "Programul merge doar pe calculatoare x86_64 (64 de biți)."

spune "Caut Python 3.10–3.12…"
PY=""
for candidat in python3.12 python3.11 python3.10 python3; do
  if command -v "$candidat" >/dev/null 2>&1; then
    if "$candidat" -c 'import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,12) else 1)'; then
      PY="$(command -v "$candidat")"; break
    fi
  fi
done
[ -n "$PY" ] || eroare "Nu am găsit Python 3.10–3.12. Instalează-l (de exemplu: sudo apt install python3 python3-venv) și pornește din nou."
"$PY" -c 'import venv' 2>/dev/null || eroare "Lipsește modulul venv (sudo apt install python3-venv)."

spune "Verific biblioteca de sunet (PortAudio)…"
if ldconfig -p 2>/dev/null | grep -q 'libportaudio\.so'; then
  echo "PortAudio este instalat."
else
  echo "Lipsește biblioteca PortAudio (libportaudio2): fără ea dictarea de la microfon nu merge."
  PACHET=""
  CMD_PACHET=""
  if command -v apt-get >/dev/null 2>&1; then PACHET="libportaudio2"; CMD_PACHET="sudo apt-get install -y"; # Debian/Ubuntu/Mint
  elif command -v dnf >/dev/null 2>&1; then PACHET="portaudio"; CMD_PACHET="sudo dnf install -y";          # Fedora
  elif command -v pacman >/dev/null 2>&1; then PACHET="portaudio"; CMD_PACHET="sudo pacman -S --noconfirm"; # Arch
  fi
  if [ -z "$PACHET" ]; then
    echo "Nu am recunoscut distribuția; instalează manual PortAudio. Instalarea continuă fără ea."
  else
    printf "Vrei să instalez PortAudio acum cu „%s %s”? (necesită parola de administrator) [d/N] " "$CMD_PACHET" "$PACHET"
    read -r raspuns || raspuns=""
    if [ "${raspuns:-n}" = "d" ] || [ "${raspuns:-n}" = "D" ]; then
      if $CMD_PACHET "$PACHET"; then echo "PortAudio a fost instalat."
      else echo "Instalarea PortAudio a eșuat; o poți reîncerca mai târziu. Instalarea continuă fără ea."; fi
    else
      echo "Bine; poți instala ulterior: $CMD_PACHET $PACHET"
    fi
  fi
fi

spune "Pregătesc mediul Python propriu în $MEDIU…"
mkdir -p "$DATE"
[ -x "$MEDIU/bin/python" ] || "$PY" -m venv "$MEDIU"
"$MEDIU/bin/python" -m pip install --upgrade pip >/dev/null

spune "Instalez bibliotecile (versiunile testate; fără PyTorch)…"
if ! "$MEDIU/bin/python" -m pip install \
  "faster-whisper==1.2.1" "ctranslate2==4.8.3" "av==17.1.0" "PySide6==6.8.0" \
  "sounddevice==0.5.6" "imageio-ffmpeg==0.6.0" "soundfile" ; then
  spune "O versiune fixată nu e disponibilă pentru Pythonul tău; încerc versiuni compatibile automat…"
  "$MEDIU/bin/python" -m pip install \
    "faster-whisper==1.2.1" "ctranslate2==4.8.3" "av" "PySide6" \
    "sounddevice" "imageio-ffmpeg" "numpy" "soundfile"
fi

[ -f "$SURSA/dictare_transcriere_romana/__init__.py" ] || eroare "Lipsește pachetul „dictare_transcriere_romana” lângă install.sh. Descarcă kitul complet și rulează install.sh din el."

spune "Copiez programul în $APP…"
mkdir -p "$APP"
rm -rf "$APP/dictare_transcriere_romana.nou"
cp -r "$SURSA/dictare_transcriere_romana" "$APP/dictare_transcriere_romana.nou"
find "$APP/dictare_transcriere_romana.nou" -name '__pycache__' -prune -exec rm -rf {} + || true
find "$APP/dictare_transcriere_romana.nou" -name '*.bak-*' -delete || true
# Sursele copiate se curăță și ele de eventuale \r (apărare dublă, pe lângă auto-corectarea de la început).
find "$APP/dictare_transcriere_romana.nou" -name '*.py' -exec sed -i 's/\r$//' {} +
rm -rf "$APP/dictare_transcriere_romana"
mv "$APP/dictare_transcriere_romana.nou" "$APP/dictare_transcriere_romana"

spune "Fac lansatorul și scurtătura din meniu…"
mkdir -p "$(dirname "$LANSATOR")" "$(dirname "$MENIU")"
cat > "$LANSATOR" <<LANS
#!/usr/bin/env bash
export DICTARE_DIR="$DATE"
export PYTHONPATH="$APP\${PYTHONPATH:+:\$PYTHONPATH}"
exec "$MEDIU/bin/python" -m dictare_transcriere_romana "\$@"
LANS
chmod +x "$LANSATOR"
cat > "$MENIU" <<DESK
[Desktop Entry]
Type=Application
Name=D&TED – Dictate & Transcription Express Digital
Comment=Dictare și transcriere în limba română
Exec=$LANSATOR
Icon=$APP/dictare_transcriere_romana/iconita_dictare.png
Terminal=false
Categories=AudioVideo;Office;
DESK

spune "Descarc modelul de transcriere (aprox. 1,6 GB). Cu placă NVIDIA te întreb înainte de bibliotecile CUDA (aprox. 1,2 GB de descărcat, 1,9 GB pe disc)…"
echo "Descărcarea se reia de unde a rămas dacă se întrerupe. Dacă nu reușește acum, se face la prima pornire."
"$LANSATOR" --pregateste || echo "Atenție: pregătirea nu s-a terminat; se reia automat la prima pornire."

spune "Gata! Pornește programul din meniu („D&TED – Dictate & Transcription Express Digital”) sau cu comanda: dted"
