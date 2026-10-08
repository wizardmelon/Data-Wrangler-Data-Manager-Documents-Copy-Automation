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

Un unico eseguibile, `dm-backup`, con questi sottocomandi:

| Comando | Quando | Azione |
|---|---|---|
| `dm-backup init` | **una volta, a inizio film** | Crea la struttura di cartelle del progetto (da YAML) sotto la radice del film e genera i file di riferimento per Silverstack e DaVinci Resolve. |
| `dm-backup files` | ogni giorno | Consolida i documenti del giorno nel DAY master di `DAILY_FILES` e li copia **dentro la cartella DAY già esistente** su ogni disco (dischi fissi + spola), con verifica checksum, manifest MHL e report finale. |
| `dm-backup still` / `dm-backup still --drx` | ogni giorno | Rileva il DAY, elimina i `.drx` dalla sorgente e copia sul Drive le still: degli ultimi N minuti (chiesti a schermo) oppure, con `--drx`, tutte quelle ancora col `.drx`. |
| `dm-backup config` | a inizio film e quando serve | Apre nel browser un **editor grafico** di `config.yaml` (crew, cartelle, dischi, spola, modalità still, rinomina Resolve, email…). |
| `dm-backup report <log>` | all'occorrenza | Rigenera il report HTML + PDF da un file di log esistente. |

### Struttura cartelle e flusso

```
<project_root>/            (es. .../Desktop/ISIDE)
├── TODAY_FILES/           lavoro della giornata
│   ├── 04_DRP  05_STILL  06_STILL_LAB   (nomi configurabili)
└── DAILY_FILES/
    ├── <SPOLA>/03_REPORTS               report della spola (nome = shuttle)
    └── DAYxxx_yyyymmdd/                 MASTER (creata da Silverstack = nome bin)
        └── 03_REPORTS
```

Flusso **`files`**: (1) rileva la spola montata e il numero DAY (dai nomi jpg delle still);
(2) copia i report della spola → `DAYxxx/03_REPORTS` (si ferma se mancano); (3) copia i report →
`Drive/REPORTS/DAYxxx`; (4) copia le cartelle di `TODAY_FILES` → DAY master; (5) copia il DAY
master **dentro** il DAY già esistente su ogni disco (fissi + spola); (6) svuota `TODAY_FILES`
(e rimuove la cartella spola) **solo** se la verifica checksum è ok su tutti i dischi.

Flusso **`still`**: rileva il DAY → elimina i `.drx` → chiede i minuti → copia su
`Drive/<stills>/DAYxxx` solo i `*.jpg` degli ultimi N minuti.
Con `--drx` (o `still.mode: drx` nel config) niente prompt: prima di eliminare i `.drx` individua le
still che hanno un `.drx` con lo stesso nome (= nuove, mai passate dal backup) e copia tutte quelle.
La notifica finale mostra il numero di still copiate.

Il flusso **`files`** termina con una notifica strutturata: DAY, cartelle copiate (con il numero
di file) e, per ogni volume, l'esito della verifica, ad esempio `✓ TQCC_Work01 (140 file)`.

### Come viene identificata la cartella DAY

Il nome (`DAY023_20260525`) viene **costruito**, non letto:

- **numero DAY** dai nomi dei jpg nella cartella still (`grep 'DAY[0-9][0-9][0-9]'`); menu se
  più d'uno, richiesta manuale se nessuno;
- **data** = *adesso − `day_hour_offset` ore*. Serve perché le still si esportano più volte al
  giorno (prima che esistano i report) e il lavoro può finire dopo mezzanotte: sottraendo qualche
  ora, un run delle 01:00 usa comunque il giorno di ripresa.

`day_hour_offset` è nello YAML: **8** copre le notturne tardive senza rischi (non lanci mai il
backup nelle prime ore dello stesso giorno di calendario); 6 = come lo script originale, 10 =
ancora sicuro.

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
chmod +x bin/dm-backup
cp config.example.yaml config.yaml   # poi adatta config.yaml al progetto
```

## Primo utilizzo su un nuovo film

```bash
dm-backup init          # crea la struttura del film (paths.project_root) + i file
                        # di riferimento per Silverstack e Resolve. UNA volta sola.
```

Poi, ogni giorno, `dm-backup files` e `dm-backup still` (tipicamente da Stream Deck).

## Configurazione

Tutto è in `config.yaml` (parti da [`config.example.yaml`](config.example.yaml),
che è commentato campo per campo). Il `config.yaml` reale **non va committato**
(è in `.gitignore`), perché contiene i dati del progetto.

Lo script cerca la configurazione in quest'ordine:
1. `--config /percorso/config.yaml`
2. variabile d'ambiente `DM_BACKUP_CONFIG`
3. `./config.yaml` nella cartella corrente

### Editor grafico (`dm-backup config`)

```bash
dm-backup --config /percorso/config.yaml config
```

Avvia un server **solo locale** (127.0.0.1, protetto da token) e apre una pagina con tutte le
impostazioni: pulsante *Sfoglia…* per le cartelle, elenco dei volumi montati da selezionare,
anteprima in tempo reale del pattern Resolve. Prima di salvare valida la configurazione con le
stesse regole dei comandi e **copia il file esistente in `.backups/`** (con data e ora). Le chiavi
sconosciute vengono conservate; i commenti del vecchio file no (per quelli vedi `config.example.yaml`).
Il file si può comunque modificare a mano.

**Senza Terminale:** fai doppio clic su **`Configura dm-backup.command`** (nella cartella del progetto).
Funziona da qualsiasi posizione, anche appena scaricato da GitHub; alla prima esecuzione prepara da
solo le librerie (serve internet) e, se manca `config.yaml`, parte da una configurazione vuota.
Solo la prima volta macOS può bloccare il file perché scaricato: tasto destro → *Apri* → *Apri*.
La finestra del Terminale che compare serve solo da indicatore: non c'è nulla da scrivere.
Se chiudi la scheda senza premere *Chiudi*, il server si spegne da solo dopo circa 3 minuti.

Se `today_files` / `daily_files` sono vuoti valgono `<project_root>/TODAY_FILES` e
`<project_root>/DAILY_FILES`.

### Modalità still

```yaml
still:
  mode: minutes     # "minutes" = chiede gli ultimi N minuti | "drx" = copia le still con .drx omonimo
  default_minutes: 5
  delete_drx: true
  extension: ".jpg"
```

- **`minutes`** (default): chiede a schermo quanti minuti di still copiare.
- **`drx`**: nessun prompt. Le still con un `.drx` dello stesso nome (stessa cartella, nome base
  uguale) sono quelle nuove, mai passate dal ciclo di backup, che cancella i `.drx`. Vengono
  individuate **prima** della cancellazione e copiate tutte.
- Da riga di comando `dm-backup still --drx` forza la modalità `drx` a prescindere dal config.

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

### Plugin dm-backup (consigliato)

1. Doppio clic su **`streamdeck-plugin/com.wizardmelon.dm-backup.streamDeckPlugin`** (Stream Deck lo installa).
2. Trascina sui tasti le azioni della categoria **dm-backup**:
   - **Backup file**: campo *Ore di scarto per le riprese notturne*. Vuoto = vale `day_hour_offset` del `config.yaml`.
   - **Copia still**: *Modalità* (come da config / ultimi N minuti / con `.drx`) e *Minuti*. Vuoti = vale il
     config; minuti vuoti = te li chiede a ogni copia.
   - **Configurazione**: apre l'editor grafico (se è già aperto, riapre la pagina).
3. In ogni tasto, sezione *Cartella dm-backup*: il plugin la cerca da solo; se non la trova, premi **Scegli…**.
   Il `config.yaml` è quello dentro quella cartella.

Il tasto mostra il segno di spunta a fine lavoro, o il triangolo di avviso se qualcosa è andato storto
(dettagli nei log del plugin). Un secondo clic mentre l'azione è già in corso viene rifiutato, per evitare
doppie copie. Alla prima esecuzione, se mancano le librerie Python, vengono installate in automatico
(serve internet; un minuto circa).

Per modificare il plugin: `cd streamdeck-plugin && npm install && npm run build` (serve Node.js 24), poi
`npx streamdeck pack com.wizardmelon.dm-backup.sdPlugin --output . --force` per rigenerare il file
`.streamDeckPlugin`. Chi usa solo il plugin non ha bisogno di Node.

### In alternativa: azione Run Shell Command

Si usa l'azione **Run Shell Command** del plugin **Mac Automation** (categoria *Mac Automation* nel
pannello azioni di Stream Deck). Nel campo del comando incolla il percorso di `bin/dm-backup`, il
percorso del tuo `config.yaml` e l'azione, **con gli apici singoli** attorno ai percorsi (servono se
contengono spazi, come nelle cartelle iCloud):

```bash
'/percorso/dm-backup/bin/dm-backup' --config '/percorso/dm-backup/config.yaml' files
'/percorso/dm-backup/bin/dm-backup' --config '/percorso/dm-backup/config.yaml' still
'/percorso/dm-backup/bin/dm-backup' --config '/percorso/dm-backup/config.yaml' still --drx
'/percorso/dm-backup/bin/dm-backup' --config '/percorso/dm-backup/config.yaml' config
```

Opzioni da riga di comando: `files --day-offset ORE`, `still --mode minutes|drx`, `still --minutes N`.
Un tasto per azione: `files` (backup documenti), `still` (still a minuti), `still --drx` (still con
.drx) e `config` (editor grafico).

`init` (struttura del film) si lancia dall'editor grafico: pulsante **Crea la struttura del film**; resta disponibile anche da terminale.

> **Importante:** la cartella `DAYxxx_yyyymmdd` deve **già esistere** sui dischi di
> backup (è dove Silverstack ha scaricato i file video/audio della giornata). Il comando
> `files` aggiunge i documenti *dentro* quel DAY, in merge. Se il DAY manca, lo script si
> ferma con un avviso (disco sbagliato o dailies non ancora scaricati).

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
bin/dm-backup        eseguibile unico (files/still/init/report) — puntato da Stream Deck
src/dm_backup/       pacchetto Python
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
  (`src/dm_backup/still.py`).
- Verifica integrità incrementale / resume di copie interrotte.

---

Autore dello script originale: Vanni Mastrantonio.
