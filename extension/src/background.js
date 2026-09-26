// CareerCraft AI — background service worker (MV3 module).
// Owns every network call (host permissions here bypass CORS) and the
// one-task-at-a-time lifecycle: poll → claim → open a tab → inject the
// content scripts → relay progress back to the API.
import {
  apiBase,
  isStaticOrigin,
  CONTENT_SCRIPT_FILES,
  BRIDGE_SCRIPT_ID,
  BRIDGE_SCRIPT_FILE,
  TERMINAL_STAGES,
  SESSION_KEYS,
  getPairing,
  setPairing,
  clearPairing,
  getActiveTask,
  setActiveTask,
  clearActiveTask,
} from "./common.js";

const POLL_ALARM = "poll";

// ── HTTP ────────────────────────────────────────────────────────────────

async function apiFetch(pairing, path, { method = "GET", json } = {}) {
  const url = apiBase(pairing.appOrigin) + path;
  const headers = { Authorization: `Bearer ${pairing.token}` };
  const init = { method, headers };
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(json);
  }
  try {
    const res = await fetch(url, init);
    let data = null;
    if (res.status !== 204) {
      const text = await res.text();
      if (text) {
        try {
          data = JSON.parse(text);
        } catch (e) {
          data = null;
        }
      }
    }
    return { ok: res.ok, status: res.status, data };
  } catch (e) {
    return { ok: false, status: 0, error: "network", data: null };
  }
}

function bytesToBase64(bytes) {
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

async function fetchResume(pairing, taskId) {
  const url = apiBase(pairing.appOrigin) + `/extension/device/tasks/${taskId}/resume`;
  try {
    const res = await fetch(url, { headers: { Authorization: `Bearer ${pairing.token}` } });
    if (!res.ok) return { ok: false, status: res.status };
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = /filename="?([^";]+)"?/i.exec(disposition);
    const filename = match ? match[1].trim() : "resume.pdf";
    const buf = new Uint8Array(await res.arrayBuffer());
    return { ok: true, base64: bytesToBase64(buf), filename, mime: res.headers.get("Content-Type") || "application/pdf" };
  } catch (e) {
    return { ok: false, status: 0, error: "network" };
  }
}

async function hasHostPermission(urlString) {
  try {
    const u = new URL(urlString);
    return await chrome.permissions.contains({ origins: [u.origin + "/*"] });
  } catch (e) {
    return false;
  }
}

// ── Bridge registration (content script on the web-app origin) ─────────

async function syncBridgeRegistration(appOrigin) {
  try {
    const existing = await chrome.scripting.getRegisteredContentScripts({ ids: [BRIDGE_SCRIPT_ID] });
    if (existing.length) await chrome.scripting.unregisterContentScripts({ ids: [BRIDGE_SCRIPT_ID] });
  } catch (e) {
    /* nothing registered yet */
  }
  if (!appOrigin) return;
  try {
    await chrome.scripting.registerContentScripts([
      {
        id: BRIDGE_SCRIPT_ID,
        matches: [appOrigin.replace(/\/+$/, "") + "/*"],
        js: [BRIDGE_SCRIPT_FILE],
        runAt: "document_idle",
        persistAcrossSessions: true,
      },
    ]);
  } catch (e) {
    console.warn("CareerCraft: could not register app bridge", e && e.message);
  }
}

// ── Poll / claim / open ─────────────────────────────────────────────────

let polling = false;

async function pollOnce() {
  if (polling) return;
  polling = true;
  try {
    const pairing = await getPairing();
    if (!pairing) return;

    const active = await getActiveTask();
    if (active && !TERMINAL_STAGES.has(active.stage)) {
      try {
        await chrome.tabs.get(active.tabId);
        return; // one task at a time — still working this one.
      } catch (e) {
        await clearActiveTask(); // its tab is gone; onRemoved should have caught this already.
      }
    }

    const res = await apiFetch(pairing, "/extension/device/tasks/claim", { method: "POST" });
    if (res.status === 401) {
      await clearPairing();
      await syncBridgeRegistration(null);
      await clearActiveTask();
      return;
    }
    if (res.status === 204 || !res.ok || !res.data || !res.data.job_url) return;

    const task = res.data;
    const permitted = await hasHostPermission(task.job_url);
    if (!permitted) {
      let host = task.job_url;
      try {
        host = new URL(task.job_url).hostname;
      } catch (e) {
        /* keep raw url */
      }
      await chrome.storage.session.set({ [SESSION_KEYS.HOST_PERMISSION_NEEDED]: host });
      await apiFetch(pairing, `/extension/device/tasks/${task.id}/events`, {
        method: "POST",
        json: { stage: "failed", error: `Allow the extension on ${host} from its popup` },
      });
      return;
    }

    const tab = await chrome.tabs.create({ url: task.job_url, active: true });
    await setActiveTask({ taskId: task.id, tabId: tab.id, stage: task.status || "claimed", task });
  } catch (e) {
    console.warn("CareerCraft: poll failed", e && e.message);
  } finally {
    polling = false;
  }
}

// A wake-up usually arrives right as the web app starts an application;
// its task appears a moment later, once the workflow has reserved it.
function pollBurst() {
  for (const ms of [0, 1500, 4000, 8000, 15000]) setTimeout(pollOnce, ms);
}

async function injectAndRun(tabId, task, submitting) {
  try {
    await chrome.scripting.executeScript({ target: { tabId }, files: CONTENT_SCRIPT_FILES });
    await chrome.tabs.sendMessage(tabId, { type: "RUN_TASK", task, submitting: !!submitting });
  } catch (e) {
    // Common and harmless: chrome:// pages, PDF viewer tabs, or a tab that
    // navigated away again before the script could run.
    console.warn("CareerCraft: injection skipped for tab", tabId, e && e.message);
  }
}

chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.status !== "complete") return;
  (async () => {
    const active = await getActiveTask();
    if (!active || active.tabId !== tabId) return;
    if (TERMINAL_STAGES.has(active.stage)) return;
    await injectAndRun(tabId, active.task, active.submitting);
  })();
});

chrome.tabs.onRemoved.addListener((tabId) => {
  (async () => {
    const active = await getActiveTask();
    if (!active || active.tabId !== tabId) return;
    if (!TERMINAL_STAGES.has(active.stage)) {
      const pairing = await getPairing();
      if (pairing) {
        await apiFetch(pairing, `/extension/device/tasks/${active.taskId}/events`, {
          method: "POST",
          json: { stage: "cancelled", message: "Tab closed" },
        });
      }
    }
    await clearActiveTask();
  })();
});

// ── Messages ─────────────────────────────────────────────────────────────

async function handleMessage(msg, sender) {
  switch (msg && msg.type) {
    case "WAKE":
    case "CC_CHECK_NOW": {
      pollBurst();
      return { ok: true };
    }

    case "CC_PLAN": {
      const pairing = await getPairing();
      if (!pairing) return { error: "not_paired" };
      const res = await apiFetch(pairing, `/extension/device/tasks/${msg.taskId}/plan`, {
        method: "POST",
        json: { url: msg.url, fields: msg.fields },
      });
      if (!res.ok) return { error: res.error || `http_${res.status}`, status: res.status };
      return { data: res.data };
    }

    case "CC_EVENT": {
      const pairing = await getPairing();
      if (!pairing) return { error: "not_paired" };
      const res = await apiFetch(pairing, `/extension/device/tasks/${msg.taskId}/events`, {
        method: "POST",
        json: {
          stage: msg.stage,
          message: msg.message,
          confirmation_text: msg.confirmation_text,
          confirmation_url: msg.confirmation_url,
          error: msg.error,
        },
      });
      if (!res.ok) return { error: res.error || `http_${res.status}`, status: res.status, active: false };
      const active = await getActiveTask();
      if (active && active.taskId === msg.taskId) {
        if (TERMINAL_STAGES.has(msg.stage) || res.data.active === false) {
          await clearActiveTask();
        } else {
          await setActiveTask({ ...active, stage: msg.stage });
        }
      }
      return { data: res.data };
    }

    case "CC_MARK_SUBMITTING": {
      const active = await getActiveTask();
      if (active && active.taskId === msg.taskId) await setActiveTask({ ...active, submitting: true });
      return { ok: true };
    }

    case "CC_ANSWER": {
      const pairing = await getPairing();
      if (!pairing) return { error: "not_paired" };
      const res = await apiFetch(pairing, "/extension/device/answers", {
        method: "POST",
        json: { label: msg.label, value: msg.value, question_key: msg.question_key },
      });
      if (!res.ok) return { error: res.error || `http_${res.status}` };
      return { data: res.data };
    }

    case "CC_DECIDE": {
      const pairing = await getPairing();
      if (!pairing) return { error: "not_paired" };
      const res = await apiFetch(pairing, "/extension/device/decide", {
        method: "POST",
        json: { state: msg.state, questions: msg.questions },
      });
      if (!res.ok) return { error: res.error || `http_${res.status}` };
      return { data: res.data };
    }

    case "CC_RESUME": {
      const pairing = await getPairing();
      if (!pairing) return { error: "not_paired" };
      const result = await fetchResume(pairing, msg.taskId);
      if (!result.ok) return { error: result.error || `http_${result.status}`, status: result.status };
      return { data: result };
    }

    case "CC_GET_STATUS": {
      const pairing = await getPairing();
      const active = await getActiveTask();
      const { [SESSION_KEYS.HOST_PERMISSION_NEEDED]: hostPermissionNeeded } = await chrome.storage.session.get(
        SESSION_KEYS.HOST_PERMISSION_NEEDED
      );
      if (!pairing) return { paired: false, hostPermissionNeeded: hostPermissionNeeded || null };
      const me = await apiFetch(pairing, "/extension/device/me");
      if (me.status === 401) {
        await clearPairing();
        await syncBridgeRegistration(null);
        return { paired: false, hostPermissionNeeded: hostPermissionNeeded || null };
      }
      return {
        paired: true,
        appOrigin: pairing.appOrigin,
        device: me.ok ? me.data : null,
        activeTask: active,
        hostPermissionNeeded: hostPermissionNeeded || null,
      };
    }

    case "CC_VALIDATE_AND_PAIR": {
      const pairing = { appOrigin: msg.appOrigin.replace(/\/+$/, ""), token: msg.token };
      const me = await apiFetch(pairing, "/extension/device/me");
      if (!me.ok || !me.data) {
        return { ok: false, error: me.status === 401 ? "Invalid or expired connection code" : "Could not reach CareerCraft AI at that URL" };
      }
      await setPairing(pairing);
      await syncBridgeRegistration(pairing.appOrigin);
      pollOnce();
      return { ok: true, device: me.data };
    }

    case "CC_PAIR_FROM_BRIDGE": {
      const appOrigin = String(msg.appOrigin || "").replace(/\/+$/, "");
      // A page can only (re)pair the extension to its own origin, and never
      // take over a pairing to a different CareerCraft deployment — that
      // needs the popup.
      const current = await getPairing();
      if (current && current.appOrigin !== appOrigin) return { ok: false, reason: "paired_elsewhere" };
      if (!isStaticOrigin(appOrigin)) {
        const granted = await chrome.permissions.contains({ origins: [appOrigin + "/*"] });
        if (!granted) return { ok: false, reason: "permission_required" };
      }
      const pairing = { appOrigin, token: msg.token };
      const me = await apiFetch(pairing, "/extension/device/me");
      if (!me.ok || !me.data) return { ok: false, reason: "invalid_token" };
      await setPairing(pairing);
      await syncBridgeRegistration(appOrigin);
      pollOnce();
      return { ok: true };
    }

    case "CC_DISCONNECT": {
      await clearPairing();
      await clearActiveTask();
      await syncBridgeRegistration(null);
      return { ok: true };
    }

    default:
      return { error: "unknown_message" };
  }
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  handleMessage(msg, sender).then(sendResponse);
  return true; // keep the channel open for the async response
});

// ── Startup ───────────────────────────────────────────────────────────────

async function init() {
  try {
    chrome.alarms.create(POLL_ALARM, { periodInMinutes: 0.5 });
  } catch (e) {
    /* alarms API unavailable in some test harnesses */
  }
  const pairing = await getPairing();
  if (pairing) await syncBridgeRegistration(pairing.appOrigin);
  pollOnce();
}

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === POLL_ALARM) pollOnce();
});
chrome.runtime.onInstalled.addListener(() => {
  init();
});
chrome.runtime.onStartup.addListener(() => {
  init();
});

// A service worker can be evicted and later woken by the alarm/message
// listeners above without onInstalled/onStartup firing again — make sure
// the poll alarm exists whenever the worker (re)loads.
init();
