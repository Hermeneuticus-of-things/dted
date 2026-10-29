#!/usr/bin/env bash
# Instalare de la ultima versiune publicată pe GitHub — varianta de Linux.
# Folosire (o singură linie, ca varianta de Windows):
#   curl -fsSL https://raw.githubusercontent.com/Hermeneuticus-of-things/dted/main/dted-bootstrap.sh | bash
# sau, descărcat:  ./dted-bootstrap.sh
# Ce face: găsește release-ul stabil „latest”, descarcă arhiva
# dted-<versiune>-linux.tar.gz, îi verifică SHA-256 din SHA256SUMS.txt
# (instalarea e refuzată dacă nu se potrivește), apoi pornește ./install.sh.
set -eu

REPO="Hermeneuticus-of-things/dted"
API="https://api.github.com/repos/$REPO/releases/latest"
DEST="${TMPDIR:-/tmp}/dted-install-$$"
UA="DTED-Bootstrap-Linux/1.0"

spune() { printf '\n==> %s\n' "$*"; }
eroare() { printf '\nEROARE: %s\n' "$*" >&2; exit 1; }

for unealta in curl tar sha256sum; do
  command -v "$unealta" >/dev/null 2>&1 || eroare "Lipsește „$unealta”. Instaleaz-o (de exemplu cu managerul de pachete al distribuției) și pornește din nou."
done

# Curățenie la ieșire, chiar și la eroare
trap 'rm -rf "$DEST"' EXIT
mkdir -p "$DEST"

spune "D&TED — caut ultima versiune publicată…"
RELEASE="$(curl -fsSL -H "Accept: application/vnd.github+json" -H "User-Agent: $UA" "$API")" || \
  eroare "Nu am putut întreba GitHub despre ultimul release (verifică conexiunea la internet)."

VERSIUNE="$(printf '%s' "$RELEASE" | grep -o '"tag_name": *"[^"]*"' | head -1 | sed 's/.*"v\([0-9.]*\)".*/\1/')"
[ -n "$VERSIUNE" ] || eroare "GitHub nu a returnat un release stabil D&TED cu eticheta v<versiune>."

ARHIVA="dted-$VERSIUNE-linux.tar.gz"
URL_ARHIVA="$(printf '%s' "$RELEASE" | grep -o "\"browser_download_url\": *\"[^\"]*$ARHIVA\"" | head -1 | sed 's/.*"\(https[^"]*\)".*/\1/')"
URL_SUME="$(printf '%s' "$RELEASE" | grep -o '"browser_download_url": *"[^"]*SHA256SUMS.txt"' | head -1 | sed 's/.*"\(https[^"]*\)".*/\1/')"
[ -n "$URL_ARHIVA" ] && [ -n "$URL_SUME" ] || \
  eroare "Release-ul v$VERSIUNE nu conține $ARHIVA și SHA256SUMS.txt așteptate."

spune "Descarc $ARHIVA…"
curl -fSL --retry 3 -H "User-Agent: $UA" -o "$DEST/$ARHIVA" "$URL_ARHIVA"
curl -fsSL --retry 3 -H "User-Agent: $UA" -o "$DEST/SHA256SUMS.txt" "$URL_SUME"

AMPRENTE="$(grep -E "^[0-9a-fA-F]{64}[[:space:]]+\*?$ARHIVA[[:space:]]*$" "$DEST/SHA256SUMS.txt" || true)"
[ "$(printf '%s\n' "$AMPRENTE" | grep -c .)" = "1" ] || \
  eroare "SHA-256 lipsește sau e duplicat pentru $ARHIVA în SHA256SUMS.txt."
AMPRENTE="$(printf '%s\n' "$AMPRENTE" | cut -d' ' -f1 | tr 'A-F' 'a-f')"

spune "Verific SHA-256…"
echo "$AMPRENTE  $DEST/$ARHIVA" | sha256sum -c --quiet || {
  rm -f "$DEST/$ARHIVA"
  eroare "Verificarea SHA-256 a eșuat pentru $ARHIVA; instalarea a fost refuzată."
}
echo "SHA-256 verificat: $ARHIVA"

spune "Dezarhivez și pornesc instalarea D&TED $VERSIUNE…"
tar -xzf "$DEST/$ARHIVA" -C "$DEST"
cd "$DEST"

# Kiturile construite pe Windows (până la 0.6.11) pot conține install.sh cu
# terminatoare CRLF, care crapă pe Linux. Dacă scriptul din arhivă nu se
# poate parsa, îl rulează dintr-o copie curățată de \r.
INSTALARE="./install.sh"
if ! bash -n "$INSTALARE" 2>/dev/null; then
  echo "Note: install.sh din arhivă are linii Windows (CRLF); îl rulez curățat."
  tr -d '\r' < "$INSTALARE" > "$DEST/install-curatat.sh"
  INSTALARE="$DEST/install-curatat.sh"
fi
bash "$INSTALARE"
