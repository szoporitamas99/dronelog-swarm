/* DroneLog: framework-free, same-origin client. All mission data comes from the API. */
"use strict";

const $ = (selector) => document.querySelector(selector);
const TOKEN_KEY = "dronelog_admin_token";
const STATUS = Object.freeze({ planned: "Tervezett", active: "Folyamatban", completed: "Befejezett" });
const FIELD_NAMES = Object.freeze({ title: "Megnevezés", location: "Helyszín", aircraft: "Drón", mission_date: "Dátum", flight_minutes: "Repülési idő", status: "Állapot", notes: "Megjegyzés" });
const state = { missions: [], total: 0, filter: "all", query: "", token: "", editingId: null, deletingId: null, loaded: false, loading: false, authCallback: null, toastTimer: null };

try { state.token = sessionStorage.getItem(TOKEN_KEY) || ""; } catch (_) { /* Storage can be disabled. Keep the token only in memory. */ }

function icon(name, className = "icon") {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", className);
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `#i-${name}`);
  svg.append(use);
  return svg;
}
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function setToken(token) {
  state.token = token;
  try { if (token) sessionStorage.setItem(TOKEN_KEY, token); else sessionStorage.removeItem(TOKEN_KEY); } catch (_) { /* In-memory mode remains usable. */ }
  $("#auth-button").classList.toggle("unlocked", Boolean(token));
  $("#auth-button-label").textContent = token ? "Szerkesztés lezárása" : "Szerkesztés engedélyezése";
  $("#access-label").textContent = token ? "Szerkesztési mód engedélyezve" : "Nyilvános, csak olvasható nézet";
  if (state.loaded) renderMissions();
}
function toast(message) {
  clearTimeout(state.toastTimer);
  $("#toast-message").textContent = message;
  $("#toast").hidden = false;
  state.toastTimer = setTimeout(() => { $("#toast").hidden = true; }, 4500);
}
function apiErrorMessage(body, fallback) {
  if (typeof body?.detail === "string") return body.detail;
  if (Array.isArray(body?.detail)) {
    return body.detail.map((item) => {
      const field = item.loc?.find((part) => Object.hasOwn(FIELD_NAMES, part));
      return field ? `${FIELD_NAMES[field]}: hibás vagy hiányzó érték.` : "Ellenőrizd a megadott adatokat.";
    }).filter((text, index, all) => all.indexOf(text) === index).join(" ");
  }
  return fallback;
}
async function api(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12000);
  const headers = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.auth) headers["X-Admin-Token"] = options.token ?? state.token;
  try {
    const response = await fetch(`/api${path}`, { method: options.method || "GET", headers, body: options.body === undefined ? undefined : JSON.stringify(options.body), cache: "no-store", credentials: "same-origin", signal: controller.signal });
    const instance = response.headers.get("X-Instance-ID");
    if (instance) $("#instance").textContent = instance;
    let body = null;
    if (response.status !== 204) {
      const contentType = response.headers.get("Content-Type") || "";
      if (contentType.includes("application/json")) body = await response.json();
    }
    if (!response.ok) {
      const error = new Error(apiErrorMessage(body, `A kiszolgáló hibát jelzett (HTTP ${response.status}).`));
      error.status = response.status;
      throw error;
    }
    if (response.status !== 204 && body === null) throw new Error("A kiszolgáló nem a várt formátumban válaszolt.");
    return body;
  } catch (error) {
    if (error.name === "AbortError" || error instanceof TypeError) {
      const message = options.method && options.method !== "GET"
        ? "A kapcsolat megszakadt. A művelet eredménye bizonytalan: frissítsd a listát, mielőtt újra mentenél."
        : "Az alkalmazás most nem éri el az API-t. Ellenőrizd, hogy a szolgáltatások és a tunnel futnak-e, majd próbáld újra.";
      throw new Error(message);
    }
    throw error;
  } finally { clearTimeout(timer); }
}
function connection(ok, instance) {
  $("#connection-dot").className = `status-dot ${ok ? "ok" : "error"}`;
  $("#connection-label").textContent = ok ? "API és adatbázis elérhető" : "A kapcsolat ellenőrzést igényel";
  if (instance) $("#instance").textContent = instance;
}
async function checkHealth() {
  try {
    const health = await api("/health");
    if (health.status !== "ok" || health.database !== "ok") throw new Error("Az adatbázis még nem áll készen.");
    connection(true, health.instance);
    return true;
  } catch (_) { connection(false); return false; }
}
function setBanner(message) {
  $("#error-message").textContent = message || "";
  $("#error-banner").hidden = !message;
}
async function loadData() {
  if (state.loading) return;
  state.loading = true;
  $("#refresh-button").disabled = true;
  $("#missions").setAttribute("aria-busy", "true");
  try {
    const [missions, stats, health] = await Promise.all([api("/missions?limit=500&offset=0"), api("/stats"), api("/health")]);
    if (!Array.isArray(missions.items) || !Number.isFinite(missions.count)) throw new Error("A feladatlista formátuma nem megfelelő.");
    state.missions = missions.items;
    state.total = missions.count;
    state.loaded = true;
    for (const field of ["total", "planned", "active", "completed"]) $("#stat-" + field).textContent = String(stats[field] ?? "–");
    $("#nav-count").textContent = String(stats.total ?? state.total);
    $("#flight-total").textContent = `${Number(stats.flight_minutes || 0).toLocaleString("hu-HU")} perc`;
    $("#updated-at").textContent = `Frissítve: ${new Intl.DateTimeFormat("hu-HU", { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date())}`;
    connection(health.status === "ok" && health.database === "ok", health.instance);
    setBanner("");
    renderMissions();
  } catch (error) {
    setBanner(error.message);
    connection(false);
    if (!state.loaded) {
      $("#list-count").textContent = "Nem elérhető";
      renderEmpty("Nincs kapcsolat a feladatnaplóval", "A lista a kapcsolat helyreállása után tölthető be.", "info");
    }
  } finally {
    state.loading = false;
    $("#refresh-button").disabled = false;
    $("#missions").setAttribute("aria-busy", "false");
  }
}
function normalise(value) { return String(value || "").normalize("NFD").replace(/\p{Diacritic}/gu, "").toLocaleLowerCase("hu"); }
function formatDate(value) {
  const date = new Date(`${value}T12:00:00`);
  return Number.isNaN(date.getTime()) ? String(value) : new Intl.DateTimeFormat("hu-HU", { year: "numeric", month: "short", day: "numeric" }).format(date);
}
function metaRow(iconName, value) {
  const row = element("div", "meta-row");
  row.append(icon(iconName), element("span", "", value));
  return row;
}
function renderEmpty(title, description, iconName = "drone") {
  const empty = element("div", "empty-state");
  empty.append(icon(iconName), element("h3", "", title), element("p", "", description));
  $("#missions").replaceChildren(empty);
}
function renderMissions() {
  const query = normalise(state.query);
  const visible = state.missions.filter((item) => (state.filter === "all" || item.status === state.filter) && (!query || normalise(`${item.title} ${item.location} ${item.aircraft} ${item.notes}`).includes(query)));
  const capped = state.total > state.missions.length;
  $("#list-count").textContent = query || state.filter !== "all"
    ? `${visible.length} találat${capped ? " az első 500-ból" : ""}`
    : capped ? `${state.missions.length} / ${state.total} · legújabb` : `${state.total} feladat`;
  if (!visible.length) {
    if (state.missions.length) renderEmpty("Nincs megfelelő feladat", "Módosítsd a keresést, vagy válassz másik állapotot.", "search");
    else renderEmpty("Még nincs feladat a naplóban", "Az Új feladat gombbal hozhatod létre az első bejegyzést.");
    return;
  }
  const fragment = document.createDocumentFragment();
  for (const mission of visible) {
    const card = element("article", "mission-card");
    const body = element("div", "mission-body");
    const top = element("div", "card-top");
    const mark = element("span", "mission-mark"); mark.append(icon("drone"));
    const status = Object.hasOwn(STATUS, mission.status) ? mission.status : "planned";
    top.append(mark, element("span", `status-pill ${status}`, STATUS[status]));
    const title = element("h3", "", mission.title);
    title.id = `mission-title-${mission.id}`;
    card.setAttribute("aria-labelledby", title.id);
    body.append(top, title, element("p", "aircraft", mission.aircraft));
    const meta = element("div", "mission-meta");
    const pair = element("div", "meta-pair");
    pair.append(metaRow("calendar", formatDate(mission.mission_date)), metaRow("clock", `${mission.flight_minutes} perc`));
    meta.append(metaRow("location", mission.location), pair);
    body.append(meta);
    if (mission.notes) {
      const notes = element("p", "mission-notes", mission.notes);
      notes.title = mission.notes;
      body.append(notes);
    }
    const footer = element("div", "card-footer");
    footer.append(element("span", "mission-id", `DL-${String(mission.id).padStart(4, "0")}`));
    if (state.token) {
      const actions = element("div", "card-actions");
      const edit = element("button", "text-button", "Szerkesztés"); edit.type = "button";
      edit.prepend(icon("edit"));
      edit.setAttribute("aria-label", `${mission.title} szerkesztése`);
      edit.addEventListener("click", () => openMission(mission));
      const remove = element("button", "icon-button delete-button"); remove.type = "button";
      remove.append(icon("trash")); remove.title = "Feladat törlése";
      remove.setAttribute("aria-label", `${mission.title} törlése`);
      remove.addEventListener("click", () => openDelete(mission));
      actions.append(edit, remove); footer.append(actions);
    } else {
      const readOnly = element("span", "read-only-label", "Csak olvasás");
      readOnly.prepend(icon("lock")); footer.append(readOnly);
    }
    card.append(body, footer); fragment.append(card);
  }
  $("#missions").replaceChildren(fragment);
}
function showAuth(callback = null) {
  state.authCallback = callback;
  $("#auth-form").reset();
  $("#auth-error").hidden = true;
  $("#auth-dialog").showModal();
  $("#admin-token").focus();
}
function todayLocal() {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}
function openMission(mission = null) {
  if (!state.token) { showAuth(() => openMission(mission)); return; }
  state.editingId = mission?.id ?? null;
  const form = $("#mission-form"); form.reset();
  $("#mission-error").hidden = true;
  $("#mission-dialog-title").textContent = mission ? "Feladat szerkesztése" : "Új drónos feladat";
  $("#mission-dialog-eyebrow").textContent = mission ? `DL-${String(mission.id).padStart(4, "0")} MÓDOSÍTÁSA` : "ÚJ BEJEGYZÉS";
  form.elements.namedItem("mission_date").value = todayLocal();
  if (mission) for (const name of Object.keys(FIELD_NAMES)) form.elements.namedItem(name).value = mission[name] ?? "";
  $("#mission-dialog").showModal();
  form.elements.namedItem("title").focus();
}
function setDialogBusy(dialog, busy) {
  dialog.dataset.busy = String(busy);
  dialog.setAttribute("aria-busy", String(busy));
  for (const button of dialog.querySelectorAll("button")) button.disabled = busy;
}
function showMutationError(target, error) {
  const label = $(target);
  label.textContent = error.status === 401 ? "A szerkesztői token nem érvényes. Zárd be az ablakot, és engedélyezd újra a szerkesztést." : error.message;
  label.hidden = false;
  if (error.status === 401) setToken("");
}
function openDelete(mission) {
  if (!state.token) { showAuth(() => openDelete(mission)); return; }
  state.deletingId = mission.id;
  $("#delete-description").textContent = `A(z) „${mission.title}” feladatot eltávolítod a közös naplóból.`;
  $("#delete-error").hidden = true;
  $("#delete-dialog").showModal();
  $("#delete-dialog [data-close]").focus();
}

$("#auth-button").addEventListener("click", () => {
  if (state.token) { setToken(""); toast("A szerkesztési mód lezárva."); } else showAuth();
});
$("#auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const token = $("#admin-token").value.trim();
  if (!token) return;
  const dialog = $("#auth-dialog"); setDialogBusy(dialog, true);
  $("#auth-error").hidden = true;
  try {
    await api("/admin/check", { auth: true, token });
    setToken(token);
    const callback = state.authCallback;
    dialog.close();
    toast("Szerkesztési hozzáférés engedélyezve.");
    if (callback) callback();
  } catch (error) { $("#auth-error").textContent = error.message; $("#auth-error").hidden = false; }
  finally { setDialogBusy(dialog, false); }
});
$("#mission-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  if (!form.reportValidity()) return;
  const data = Object.fromEntries(new FormData(form).entries());
  for (const key of ["title", "location", "aircraft", "notes"]) data[key] = data[key].trim();
  data.flight_minutes = Number(data.flight_minutes);
  const dialog = $("#mission-dialog"); setDialogBusy(dialog, true);
  $("#mission-error").hidden = true;
  const isEdit = state.editingId !== null;
  try {
    await api(isEdit ? `/missions/${state.editingId}` : "/missions", { method: isEdit ? "PATCH" : "POST", body: data, auth: true });
    dialog.close();
    toast(isEdit ? "A feladat módosításait elmentettük." : "Az új feladat bekerült a naplóba.");
    await loadData();
  } catch (error) { showMutationError("#mission-error", error); }
  finally { setDialogBusy(dialog, false); }
});
$("#confirm-delete").addEventListener("click", async () => {
  if (state.deletingId === null) return;
  const dialog = $("#delete-dialog"); setDialogBusy(dialog, true);
  try {
    await api(`/missions/${state.deletingId}`, { method: "DELETE", auth: true });
    dialog.close(); state.deletingId = null;
    toast("A feladatot töröltük a naplóból.");
    await loadData();
  } catch (error) { showMutationError("#delete-error", error); }
  finally { setDialogBusy(dialog, false); }
});
for (const button of document.querySelectorAll("[data-close]")) button.addEventListener("click", () => {
  const dialog = document.getElementById(button.dataset.close);
  if (dialog.dataset.busy !== "true") dialog.close();
});
for (const dialog of document.querySelectorAll("dialog")) dialog.addEventListener("cancel", (event) => { if (dialog.dataset.busy === "true") event.preventDefault(); });
$("#auth-dialog").addEventListener("close", () => { $("#admin-token").value = ""; state.authCallback = null; });
$("#architecture-button").addEventListener("click", () => $("#architecture-dialog").showModal());
$("#new-mission").addEventListener("click", () => openMission());
$("#refresh-button").addEventListener("click", loadData);
$("#retry-button").addEventListener("click", loadData);
$("#instance-refresh").addEventListener("click", async () => {
  $("#instance-refresh").disabled = true;
  await checkHealth();
  $("#instance-refresh").disabled = false;
});
$("#search").addEventListener("input", (event) => { state.query = event.target.value; if (state.loaded) renderMissions(); });
for (const button of document.querySelectorAll("[data-filter]")) button.addEventListener("click", () => {
  state.filter = button.dataset.filter;
  for (const filter of document.querySelectorAll("[data-filter]")) { const selected = filter === button; filter.classList.toggle("selected", selected); filter.setAttribute("aria-pressed", String(selected)); }
  if (state.loaded) renderMissions();
});

// A restored token is validated before the interface enables write controls.
(async () => {
  const savedToken = state.token;
  state.token = "";
  await loadData();
  if (savedToken) {
    try { await api("/admin/check", { auth: true, token: savedToken }); setToken(savedToken); }
    catch (_) { setToken(""); }
  }
})();
// Poll only the readiness endpoint; do not overwrite forms or reload the task list.
setInterval(() => { if (!document.hidden && !state.loading) checkHealth(); }, 30000);
