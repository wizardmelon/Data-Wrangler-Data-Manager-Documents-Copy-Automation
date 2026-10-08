#!/bin/bash
# Doppio clic per aprire l'editor grafico di dm-backup (si apre nel browser).
# Funziona da qualsiasi posizione: usa la cartella in cui si trova questo file.
# Alla prima esecuzione prepara da solo le librerie necessarie (serve internet).
cd "$(dirname "$0")" || exit 1
DIR="$(pwd)"

echo "dm-backup · editor di configurazione"
echo "Non chiudere questa finestra finché usi l'editor (premi 'Chiudi' nella pagina per uscire)."
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 non trovato. Se macOS propone di installare gli strumenti da riga di comando, accetta e rilancia."
  read -r -p "Premi Invio per chiudere…" _; exit 1
fi

PY=python3
if [ -x "$DIR/.venv/bin/python" ]; then
  PY="$DIR/.venv/bin/python"
elif ! python3 -c "import yaml, reportlab" >/dev/null 2>&1; then
  echo "Prima esecuzione: preparo le librerie necessarie (un minuto circa)…"
  if python3 -m venv "$DIR/.venv" && "$DIR/.venv/bin/pip" install -q --disable-pip-version-check -r "$DIR/requirements.txt"; then
    PY="$DIR/.venv/bin/python"
  else
    echo "Installazione non riuscita. Controlla la connessione internet e riprova."
    rm -rf "$DIR/.venv"
    read -r -p "Premi Invio per chiudere…" _; exit 1
  fi
fi

exec "$PY" "$DIR/bin/dm-backup" --config "$DIR/config.yaml" config
