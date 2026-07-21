# Script originale — `00_DOCUMENTS.scpt` (AppleScript, v1.4)

> Trascrizione leggibile dello script AppleScript **compilato** originale, scritto
> da Vanni Mastrantonio. Conservata come riferimento storico: il `.scpt` binario
> non è versionabile/diffabile, quindi questa è la ricostruzione della logica e
> della documentazione interna ottenuta decompilando lo script. Il nuovo software
> Python in questo repository sostituisce questo file.

- **Versione:** 1.4 (STABILE) — rilascio 15 Ottobre 2025
- **Autore:** Vanni Mastrantonio
- **Scopo:** a fine giornata copia i file di progetto (report Silverstack + cartelle
  sorgente) e le still verso dischi di backup e drive condivisi. Avviato da Stream Deck.

## Variabili principali da configurare (nell'originale erano hardcoded)

- **source1, source2, sourceStill…** — percorsi delle cartelle sorgenti (DRP, ALE, STILL…),
  raccolte nell'array `sourceFolders`.
- **baseWork** — cartella principale con le giornate (`DAYxxx_yyyyMMdd`) e i report.
- **drive** — cartella del drive dove effettuare il backup.
- **disc1, disc2, …** — nomi dei dischi di backup (es. `ODC_BACKUP_01`).
- **discSpola** — nome base del disco spola (numero cercato automaticamente tra i volumi).
- **dest1, dest2, …** — destinazioni finali (una per disco), nell'array `destPaths`.
- **destinationStill** — cartella del drive dove copiare le still.
- **logFolderName** — cartella dei log.
- **film, prod, regia…** — crediti per l'intestazione del log.

## Struttura cartella REPORT richiesta

I report vanno creati dentro `baseWork` con la struttura Silverstack:

```
objectName$/REPORTS/$projectName$ $reportType$_$objectName$
```

Esempio:
```
/Users/dit/Desktop/ODC/DAILY FILES/ODC_SPOLA_03/REPORTS/
/Users/dit/Desktop/ODC/DAILY FILES/DAY010_20251122/REPORTS/
```

L'assenza della sottocartella `REPORTS` nella spola blocca lo script (presume sia
stato avviato prima della creazione dei report).

## Note tecniche e logiche automatiche

- `copyWithFind` copia tutti i file da una sorgente a una destinazione mantenendo la
  struttura interna (usava `find | xargs cp` per gestire spazi/caratteri strani).
- Se sono montate più "spole", apre un menu a tendina per chiedere quale usare.
- Se la cartella REPORT non esiste → avviso e stop.
- Ricerca automatica del numero DAY leggendo il nome di un file JPG nella cartella
  still (pattern `DAY###`). Perché funzioni, la still va esportata da Resolve con:
  `SC%{Scene}_%{Clip Name}_%{Timeline Name}`.
- Forzare l'autodetect: `run /Users/.../backup_odc.scpt still y`.

## Sistema di log (v1.4)

- Ogni operazione principale registrata in un log giornaliero dentro `SCRIPT LOGS`.
- Se il log non esiste, viene creata un'intestazione con titolo + crediti.
- `copyFolder` usava `cp -Rv` (verbose) con output formattato riga per riga nel log.
- Ogni riga: `[WHAT --> timestamp] messaggio` (WHAT = `files` o `still`).

## Esecuzione da Stream Deck

Azione "Run", Command `run`, Script = percorso allo `.scpt`, Arguments = `files` /
`still` / `still y` (SENZA virgolette). Serve accesso completo al disco (Privacy macOS).

## Flusso — modalità `files`

1. Input/auto-detect del DAY (manuale, oppure automatico dalle still con `y`).
2. Generazione nomi e percorsi (data corrente via shell `date`).
3. Ricerca disco SPOLA (menu se multipli).
4. Creazione path sorgenti e destinazioni (`destPaths`).
5. Check dischi montati e check presenza `REPORTS`.
6. Copia file REPORT nella working dir.
7. Copia cartelle sorgente nella working dir.
8. Copia `DAYxxx_zzzzzzzz` nei dischi.
9. Svuota le cartelle originali (`recreateFolder`) e rimuove la cartella report nella spola.

> ⚠️ **Punto debole dell'originale:** le cartelle sorgente venivano svuotate
> controllando solo il *conteggio* file, non l'integrità della copia. Il nuovo
> software Python cancella solo dopo verifica **checksum** su tutte le destinazioni.

## Flusso — modalità `still`

1. Autodetect del DAY dalle still (menu se multipli), input MIN da export.
2. Eliminazione DRX / pulizia sorgente.
3. Copia delle still sul drive.

## Changelog storico (dall'originale)

- **v1.4** — verbose `cp -Rv` nel log, intestazione automatica del log con crediti,
  cartella `SCRIPT LOGS`, conteggio file copiati.
- **v1.3.1** — sistema di log automatico (TXT giornaliero).
- **v1.3** — ricerca automatica del numero DAY via nome file JPG.
- **v1.2** — unione dei due script (daily files + still) in un unico script modulare,
  selezione automatica del disco SPOLA, menu per SPOLA multiple.

## Roadmap dell'autore (v1.5) — recepita nel nuovo software

- [x] Verifica integrità file copiati (md5/cmp) → checksum + MHL
- [x] Notifica finale macOS a completamento
- [ ] Opzione per forzare sovrascrittura log giornaliero
