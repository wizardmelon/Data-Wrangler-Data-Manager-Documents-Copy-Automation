// Property inspector condiviso: impostazioni del tasto + cartella dm-backup (globale).
let ws, uuid, actionInfo, settings = {};
const $ = (id) => document.getElementById(id);

function send(obj) { ws.send(JSON.stringify(obj)); }
function saveSettings() { send({ event: "setSettings", context: uuid, payload: settings }); }
function toPlugin(payload) { send({ event: "sendToPlugin", context: uuid, action: actionInfo.action, payload }); }

function bindFields() {
  document.querySelectorAll("[data-s]").forEach((el) => {
    const k = el.dataset.s;
    el.value = settings[k] ?? "";
    el.addEventListener("input", () => { settings[k] = el.value; saveSettings(); toggles(); });
  });
  toggles();
}
function toggles() {
  const m = $("minutesRow"); if (m) m.style.display = settings.mode === "drx" ? "none" : "";
}

function showFolder(p) {
  const f = $("folder"), st = $("folderStatus");
  if (!f) return;
  f.value = p.folder || "";
  if (p.error) { st.className = "hint err"; st.textContent = p.error; }
  else if (p.found) { st.className = "hint ok"; st.textContent = "✓ dm-backup trovato"; }
  else { st.className = "hint err"; st.textContent = "Cartella non trovata: scegli la cartella di dm-backup."; }
}

window.connectElgatoStreamDeckSocket = function (port, inUUID, registerEvent, _info, inActionInfo) {
  uuid = inUUID; actionInfo = JSON.parse(inActionInfo);
  settings = actionInfo.payload?.settings ?? {};
  ws = new WebSocket("ws://127.0.0.1:" + port);
  ws.onopen = () => {
    send({ event: registerEvent, uuid });
    bindFields();
    toPlugin({ cmd: "status" });
  };
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.event === "sendToPropertyInspector") showFolder(m.payload || {});
  };
  const b = $("choose");
  if (b) b.onclick = () => toPlugin({ cmd: "chooseFolder" });
};
