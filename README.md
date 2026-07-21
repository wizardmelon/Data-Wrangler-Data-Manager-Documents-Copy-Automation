# Data Wrangler / Data Manager — Documents Copy Automation

Strumenti da riga di comando per **Data Manager / DIT** sul set: copia e backup
di fine giornata dei documenti di progetto e delle still, con verifica di
integrità, log giornaliero, report per la produzione e scaffolding delle
cartelle. Pensato per essere lanciato da **Stream Deck**.

È la riscrittura in **Python** dello script AppleScript `00_DOCUMENTS.scpt` (v1.4).
La logica dell'originale è conservata in [`legacy/00_DOCUMENTS_v1.4.md`](legacy/00_DOCUMENTS_v1.4.md).

## Perché non più AppleScript

- Il `.scpt` compilato **non è versionabile né diffabile** in git.
- La copia era dentro stringhe `do shell script` (`cp -Rv`), **fragile** e **senza
  verifica d'integrità reale**: le sorgenti venivano cancellate controllando solo
  il *conteggio* file. Se una copia falliva in silenzio, si perdeva l'originale.
- I dati di progetto erano **hardcoded**: per ogni produzione si editava il codice.

## Cosa fa

| Comando | Azione |
|---|---|
| `backup_odc files` | Assembla i documenti del giorno (REPORTS + cartelle sorgente) e li copia **dentro la cartella DAY già esistente** su ogni disco di backup, con verifica checksum, manifest MHL e report finale. |
| `backup_odc still` | Rileva automaticamente il DAY dai nomi delle still (`DAY###`) e le copia sul drive, con verifica. |
| `backup_odc init` (o `odc_init`) | Crea la struttura cartelle della giornata (da YAML) e genera i file di riferimento per Silverstack e DaVinci Resolve. |
| `backup_odc report <log>` | Rigenera il report HTML + PDF da un file di log esistente. |

### Miglioramenti rispetto all'originale

- **Copia con `rsync`** (fallback Python se assente): gestisce nativamente spazi e
  caratteri strani nei nomi.
- **Verifica checksum** sorgente↔destinazione: le sorgenti si svuotano **solo** se
  la verifica passa su **tutte** le destinazioni.
- **Manifest MHL** (Media Hash List) per ogni copia, come prova d'integrità.
- **Controllo spazio libero** preventivo sui dischi.
- **Notifica macOS** a fine operazione.
- **Report giornaliero** HTML + PDF pronto per la produzione.
- **Configurazione per-progetto in YAML**: il codice non si tocca mai.

## Requisiti

- macOS con **Accesso completo al disco** per l'app che lancia lo script
  (Stream Deck o Terminale) — Impostazioni → Privacy e sicurezza.
- Python 3.9+ (macOS recente lo include; in alternativa `brew install python`).
- Dipendenze Python: `pip3 install -r requirements.txt` (PyYAML, reportlab).
- `rsync` è usato se presente (di serie su macOS); altrimenti si usa un fallback Python.

## Installazione

```bash
git clone <questo-repo>
cd Data-Wrangler-Data-Manager-Documents-Copy-Automation
pip3 install -r requirements.txt
chmod +x bin/backup_odc bin/odc_init
cp config.example.yaml config.yaml   # poi adatta config.yaml al progetto
```

## Configurazione

Tutto è in `config.yaml` (parti da [`config.example.yaml`](config.example.yaml),
che è commentato campo per campo). Il `config.yaml` reale **non va committato**
(è in `.gitignore`), perché contiene i dati del progetto.

Lo script cerca la configurazione in quest'ordine:
1. `--config /percorso/config.yaml`
2. variabile d'ambiente `ODC_CONFIG`
3. `./config.yaml` nella cartella corrente

### Pattern rinomina still (DaVinci Resolve)

Nello YAML scrivi **in parole semplici** cosa vuoi nel nome del file; l'eseguibile
costruisce il pattern `%{...}` da incollare in Resolve (Deliver → *File name uses:
Custom name*). **Il token che porta il DAY viene aggiunto in coda automaticamente**
— non elencarlo — perché serve alla modalità `still` per ritrovare la cartella DAY.

```yaml
still_rename:
  prefix: "SC"
  fields: [scena, clip]     # alias: scena, clip, timeline, reel, shot, take, camera, roll, program
  separator: "_"
  day_token: "timeline"     # token con "DAY###" (default: timeline)
# → SC%{Scene}_%{Clip Name}_%{Timeline Name}
```

Un alias non riconosciuto produce un errore chiaro con l'elenco di quelli validi.

### Report path Silverstack

`init` scrive anche la stringa da incollare in Silverstack:
`objectName$/REPORTS/$projectName$ $reportType$_$objectName$`. `$projectName$` lo
compila Silverstack, quindi resta letterale.

## Uso con Stream Deck

Azione **"Run"** (plugin che esegue comandi):
- Command: `run`
- Script: percorso completo a `bin/backup_odc`
- Arguments (SENZA virgolette): `files` oppure `still`

Esempi:
```
run /Users/dit/.../bin/backup_odc files
run /Users/dit/.../bin/backup_odc still
run /Users/dit/.../bin/odc_init
```

> **Importante:** la cartella `DAYxxx_yyyyMMdd` deve **già esistere** sui dischi di
> backup (è dove sono stati scaricati i file video/audio della giornata). Il comando
> `files` aggiunge i documenti *dentro* quel DAY. Se il DAY manca, lo script si ferma
> con un avviso (disco sbagliato o dailies non ancora scaricati).

## Sviluppo e test

```bash
pip3 install -r requirements.txt pytest
python3 -m pytest tests/ -q
```

I test coprono la logica pura (config, pattern still + regex DAY, costruzione
percorsi, verifica DAY sul disco, scaffolding, copia+checksum+MHL, report). Le parti
che richiedono macOS reale (`osascript`, `/Volumes`) sono isolate in `gui.py` /
`diskutils.py`.

## Struttura del repository

```
bin/                 wrapper eseguibili (backup_odc, odc_init) — puntati da Stream Deck
src/odc_backup/      pacchetto Python
  config.py          caricamento/validazione YAML
  gui.py             finestre native macOS (osascript)
  diskutils.py       ricerca SPOLA, dischi montati, spazio libero
  copyops.py         copia (rsync/fallback), checksum, MHL
  daylog.py          log giornaliero con intestazione
  still.py           alias → pattern Resolve + regex DAY
  scaffold.py        comando init
  report.py          report HTML + PDF
  workflows.py       orchestrazione files/still/init/report
tests/               test unitari
config.example.yaml  template di configurazione
legacy/              trascrizione dello script AppleScript originale
```

## Estensioni future

- Modalità **dry-run** / anteprima delle operazioni distruttive.
- Nuove cartelle sorgente per `files`: già supportate, basta aggiungerle a
  `sources.folders` nello YAML.
- Nuovi token Resolve per la rinomina still: aggiungibili in `ALIAS_TO_TOKEN`
  (`src/odc_backup/still.py`).
- Verifica integrità incrementale / resume di copie interrotte.

---

Autore dello script originale: Vanni Mastrantonio.
