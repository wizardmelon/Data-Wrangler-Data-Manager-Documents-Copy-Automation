// Plugin Stream Deck per dm-backup: lancia bin/dm-run (-> dm-backup) con le impostazioni del tasto.
import { spawn, execFile } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import streamDeck, { SingletonAction } from "@elgato/streamdeck";

const UUID = "com.wizardmelon.dm-backup";
const log = streamDeck.logger;

// ---------------------------------------------------------------- cartella dm-backup
async function getFolder() {
  const g = await streamDeck.settings.getGlobalSettings();
  if (g.folder && isValidFolder(g.folder)) return g.folder;
  const found = await findFolder();
  if (found) await streamDeck.settings.setGlobalSettings({ ...g, folder: found });
  return found;
}

function isValidFolder(dir) {
  try { return fs.existsSync(path.join(dir, "bin", "dm-run")) && fs.existsSync(path.join(dir, "bin", "dm-backup")); }
  catch { return false; }
}

// Cerca la cartella con Spotlight (file "Configura dm-backup.command" nella cartella del progetto).
function findFolder() {
  return new Promise((resolve) => {
    execFile("/usr/bin/mdfind", ["-name", "Configura dm-backup.command"], { timeout: 8000 }, (err, out) => {
      if (err) return resolve(null);
      const dirs = out.split("\n").filter(Boolean).map((p) => path.dirname(p)).filter(isValidFolder);
      resolve(dirs[0] ?? null);
    });
  });
}

function chooseFolder() {
  return new Promise((resolve) => {
    execFile("/usr/bin/osascript", ["-e",
      'POSIX path of (choose folder with prompt "Scegli la cartella dm-backup (quella con config.yaml e bin)")'],
      (err, out) => resolve(err ? null : out.trim().replace(/\/$/, "")));
  });
}

// ---------------------------------------------------------------- esecuzione
const running = new Map(); // chiave -> processo

function buildEnv() {
  return { ...process.env, PATH: `/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${process.env.PATH ?? ""}` };
}

function runCommand(folder, args, { onUrl } = {}) {
  const cfg = path.join(folder, "config.yaml");
  const child = spawn("/bin/bash", [path.join(folder, "bin", "dm-run"), "--config", cfg, ...args],
    { cwd: folder, env: buildEnv(), stdio: ["ignore", "pipe", "pipe"] });
  let stderr = "";
  child.stdout.on("data", (d) => {
    const m = /(http:\/\/127\.0\.0\.1:\d+\/)/.exec(String(d));
    if (m && onUrl) onUrl(m[1]);
  });
  child.stderr.on("data", (d) => { stderr += String(d); });
  return { child, stderr: () => stderr };
}

async function execute(ev, key, args) {
  if (running.has(key)) { await ev.action.showAlert(); return; } // già in corso: evita doppie copie
  const folder = await getFolder();
  if (!folder) {
    log.error("Cartella dm-backup non trovata");
    await ev.action.showAlert();
    return;
  }
  const { child, stderr } = runCommand(folder, args);
  running.set(key, child);
  child.on("error", async (e) => { running.delete(key); log.error(String(e)); await ev.action.showAlert(); });
  child.on("close", async (code) => {
    running.delete(key);
    if (code === 0) await ev.action.showOk();
    else if (code !== 130) { log.error(`dm-backup ${args.join(" ")} -> ${code}\n${stderr()}`); await ev.action.showAlert(); }
  });
}

function numberOrNull(v) {
  if (v === undefined || v === null || String(v).trim() === "") return null;
  const n = Number(String(v).replace(",", "."));
  return Number.isFinite(n) && n >= 0 ? n : null;
}

// ---------------------------------------------------------------- azioni
class Base extends SingletonAction {
  async onSendToPlugin(ev) {
    const cmd = ev.payload?.cmd;
    if (cmd === "status") {
      const folder = await getFolder();
      await streamDeck.ui.sendToPropertyInspector({ folder: folder ?? "", found: !!folder });
    } else if (cmd === "chooseFolder") {
      const dir = await chooseFolder();
      if (!dir) return;
      if (!isValidFolder(dir)) {
        await streamDeck.ui.sendToPropertyInspector({ error: "Quella cartella non contiene bin/dm-run: scegli la cartella principale di dm-backup." });
        return;
      }
      const g = await streamDeck.settings.getGlobalSettings();
      await streamDeck.settings.setGlobalSettings({ ...g, folder: dir });
      await streamDeck.ui.sendToPropertyInspector({ folder: dir, found: true });
    }
  }
}

class FilesAction extends Base {
  manifestId = `${UUID}.files`;
  async onKeyDown(ev) {
    const args = ["files"];
    const off = numberOrNull(ev.payload.settings.offsetHours);
    if (off !== null) args.push("--day-offset", String(Math.round(off)));
    await execute(ev, "files", args);
  }
}

class StillAction extends Base {
  manifestId = `${UUID}.still`;
  async onKeyDown(ev) {
    const s = ev.payload.settings;
    const args = ["still"];
    if (s.mode === "minutes" || s.mode === "drx") args.push("--mode", s.mode);
    const min = numberOrNull(s.minutes);
    if (min !== null && s.mode !== "drx") args.push("--minutes", String(Math.round(min)));
    await execute(ev, "still", args);
  }
}

class ConfigAction extends Base {
  manifestId = `${UUID}.config`;
  url = null;
  async onKeyDown(ev) {
    if (running.has("config")) { // editor già aperto: riapri la pagina
      if (this.url) await streamDeck.system.openUrl(this.url);
      return;
    }
    const folder = await getFolder();
    if (!folder) { await ev.action.showAlert(); return; }
    const { child, stderr } = runCommand(folder, ["config"], {
      onUrl: (u) => { this.url = u; }, // la pagina la apre già dm-backup
    });
    running.set("config", child);
    child.on("error", async (e) => { running.delete("config"); log.error(String(e)); await ev.action.showAlert(); });
    child.on("close", async (code) => {
      running.delete("config");
      this.url = null;
      if (code !== 0 && code !== null) { log.error(`config -> ${code}\n${stderr()}`); await ev.action.showAlert(); }
    });
  }
}

streamDeck.actions.registerAction(new FilesAction());
streamDeck.actions.registerAction(new StillAction());
streamDeck.actions.registerAction(new ConfigAction());
streamDeck.connect();
