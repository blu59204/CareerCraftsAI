// Shared constants/helpers for the background service worker and the popup
// (both loaded as ES modules). Content scripts are classic scripts and do
// not import this — they only exchange plain messages with the background.

export const STATIC_HOST_ORIGINS = [
  "http://localhost",
  "http://127.0.0.1",
  "https://www.linkedin.com",
  "https://*.naukri.com",
  "https://www.naukri.com",
  "https://*.greenhouse.io",
  "https://jobs.lever.co",
  "https://jobs.ashbyhq.com",
  "https://*.myworkdayjobs.com",
  "https://*.indeed.com",
  "https://www.foundit.in",
  "https://www.instahyre.com",
];

export const CONTENT_SCRIPT_FILES = [
  "src/content/dom.js",
  "src/content/panel.js",
  "src/content/drivers.js",
  "src/content/runner.js",
];

export const BRIDGE_SCRIPT_ID = "careercraft-bridge";
export const BRIDGE_SCRIPT_FILE = "src/content/bridge.js";

export const TERMINAL_STAGES = new Set(["submitted", "failed", "cancelled"]);
export const OPEN_TASK_STATUSES = new Set(["claimed", "filling", "needs_input", "review", "login_required"]);

export const LOCAL_KEYS = { PAIRING: "pairing" };
export const SESSION_KEYS = { ACTIVE_TASK: "activeTask", HOST_PERMISSION_NEEDED: "hostPermissionNeeded" };

// A static host_permissions pattern is normally an exact scheme+host (with
// optional leading "*."); a plain hostname match is enough here — we only
// use this to decide whether an *additional* optional permission request
// is needed, not to enforce Chrome's own permission checks.
function hostMatchesStatic(hostname) {
  return STATIC_HOST_ORIGINS.some((origin) => {
    const bare = origin.replace(/^https?:\/\//, "");
    if (bare.startsWith("*.")) {
      const suffix = bare.slice(1); // ".naukri.com"
      return hostname === bare.slice(2) || hostname.endsWith(suffix);
    }
    return hostname === bare;
  });
}

export function isStaticOrigin(origin) {
  try {
    const u = new URL(origin);
    return hostMatchesStatic(u.hostname);
  } catch (e) {
    return false;
  }
}

export function apiBase(appOrigin) {
  return appOrigin.replace(/\/+$/, "") + "/api/v1";
}

export async function getPairing() {
  const { [LOCAL_KEYS.PAIRING]: pairing } = await chrome.storage.local.get(LOCAL_KEYS.PAIRING);
  return pairing || null;
}

export async function setPairing(pairing) {
  await chrome.storage.local.set({ [LOCAL_KEYS.PAIRING]: pairing });
}

export async function clearPairing() {
  await chrome.storage.local.remove(LOCAL_KEYS.PAIRING);
}

export async function getActiveTask() {
  const { [SESSION_KEYS.ACTIVE_TASK]: active } = await chrome.storage.session.get(SESSION_KEYS.ACTIVE_TASK);
  return active || null;
}

export async function setActiveTask(active) {
  await chrome.storage.session.set({ [SESSION_KEYS.ACTIVE_TASK]: active });
}

export async function clearActiveTask() {
  await chrome.storage.session.remove(SESSION_KEYS.ACTIVE_TASK);
}
