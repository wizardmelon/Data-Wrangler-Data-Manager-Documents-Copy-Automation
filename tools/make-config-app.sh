#!/bin/bash
# Crea "Configura dm-backup.app": doppio clic -> si apre l'editor grafico nel browser,
# senza Terminale. Uso: tools/make-config-app.sh [cartella]  (default: ~/Applications; evita cartelle iCloud)
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-$HOME/Applications}"; mkdir -p "$DEST"
APP="$DEST/Configura dm-backup.app"
BIN="$ROOT/bin/dm-backup"
CFG="$ROOT/config.yaml"
rm -rf "$APP"
osacompile -o "$APP" -e "do shell script \"'$BIN' --config '$CFG' config > /dev/null 2>&1 &\""
echo "Creata: $APP"
