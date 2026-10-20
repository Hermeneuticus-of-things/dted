#!/usr/bin/env bash
# Dictate & Transcription Express Digital (D&TED) – Dictare și transcriere în limba română
# Instalare automată pe Linux (x86_64), fără drepturi de administrator pentru program.
# Pune: mediu Python propriu (faster-whisper, ctranslate2, PyAV, PySide6, ffmpeg inclus),
# programul, o scurtătură în meniu, apoi descarcă modelul (cu SHA-256) și, doar dacă
# există placă NVIDIA, bibliotecile CUDA (cuBLAS 12, cuDNN 9) în folderul de date.
# PyTorch NU este instalat (motorul folosește CTranslate2).
set -euo pipefail

SURSA="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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
  echo "Atenție: lipsește biblioteca PortAudio (libportaudio2). Fără ea dictarea de la microfon nu merge;"
  echo "transcrierea fișierelor merge. O poți instala tu, de exemplu:"
  echo "    Debian/Ubuntu/Mint:  sudo apt install libportaudio2"
  echo "    Fedora:              sudo dnf install portaudio"
  echo "    Arch:                sudo pacman -S portaudio"
  echo "Instalarea continuă fără ea."
fi

spune "Pregătesc mediul Python propriu în $MEDIU…"
mkdir -p "$DATE"
[ -x "$MEDIU/bin/python" ] || "$PY" -m venv "$MEDIU"
"$MEDIU/bin/python" -m pip install --upgrade pip >/dev/null

spune "Instalez bibliotecile de transcriere (fără PyTorch)…"
"$MEDIU/bin/python" -m pip install \
  "faster-whisper==1.2.1" "ctranslate2==4.8.3" "av" "PySide6" \
  "sounddevice" "imageio-ffmpeg" "numpy" "soundfile"

spune "Copiez programul în $APP…"
mkdir -p "$APP"
rm -rf "$APP/dictare_transcriere_romana.nou"
cp -r "$SURSA/dictare_transcriere_romana" "$APP/dictare_transcriere_romana.nou"
find "$APP/dictare_transcriere_romana.nou" -name '__pycache__' -prune -exec rm -rf {} + || true
find "$APP/dictare_transcriere_romana.nou" -name '*.bak-*' -delete || true
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
