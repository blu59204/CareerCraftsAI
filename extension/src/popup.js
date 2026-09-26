// CareerCraft AI — toolbar popup: pairing, status and permissions.
import { isStaticOrigin } from "./common.js";

const $ = (id) => document.getElementById(id);

const STAGE_LABELS = {
  claimed: "Opening the job page",
  filling: "Filling the application",
  needs_input: "Waiting for your answers in the page",
  review: "Waiting for your review in the page",
  login_required: "Sign in to the job site in that tab",
};

function send(message) {
  return new Promise((resolve) => chrome.runtime.sendMessage(message, (response) => resolve(response || {})));
}

function showError(text) {
  $("error").textContent = text || "";
  $("error").hidden = !text;
}

async function ensureOriginPermission(origin) {
  if (isStaticOrigin(origin)) return true;
  // Must run inside the click handler: Chrome only prompts on a user gesture.
  return chrome.permissions.request({ origins: [origin.replace(/\/+$/, "") + "/*"] });
}

async function render() {
  const status = await send({ type: "CC_GET_STATUS" });
  $("pair").hidden = !!status.paired;
  $("status").hidden = !status.paired;
  if (!status.paired) return;

  const user = status.device && status.device.user;
  const who = user ? user.email || user.name : "your account";
  const device = status.device ? ` (${status.device.device_name})` : "";
  $("who").textContent = `Connected as ${who}${device}`;

  const active = status.activeTask;
  if (active && active.task) {
    const what = [active.task.company, active.task.role].filter(Boolean).join(" · ") || "Job application";
    $("task").textContent = `${what} — ${STAGE_LABELS[active.stage] || active.stage}`;
  } else {
    $("task").textContent = "No applications waiting.";
  }

  const host = status.hostPermissionNeeded;
  $("permission").hidden = !host;
  if (host) $("permission-text").textContent = `Allow the extension on ${host} to apply there, then start the application again from CareerCraft.`;
}

$("connect").addEventListener("click", async () => {
  showError("");
  const appOrigin = $("app-origin").value.trim().replace(/\/+$/, "");
  const token = $("token").value.trim();
  if (!/^https?:\/\//.test(appOrigin)) return showError("Enter the full CareerCraft URL, e.g. https://app.example.com");
  if (!token.startsWith("ccx_")) return showError("Paste the connection code from CareerCraft (it starts with ccx_).");
  if (!(await ensureOriginPermission(appOrigin))) return showError("The extension needs access to your CareerCraft site to connect.");
  $("connect").disabled = true;
  const result = await send({ type: "CC_VALIDATE_AND_PAIR", appOrigin, token });
  $("connect").disabled = false;
  if (!result.ok) return showError(result.error || "Could not connect.");
  $("token").value = "";
  render();
});

$("check").addEventListener("click", async () => {
  await send({ type: "CC_CHECK_NOW" });
  setTimeout(render, 1500);
});

$("disconnect").addEventListener("click", async () => {
  await send({ type: "CC_DISCONNECT" });
  render();
});

$("grant").addEventListener("click", async () => {
  const status = await send({ type: "CC_GET_STATUS" });
  const host = status.hostPermissionNeeded;
  if (!host) return;
  const granted = await chrome.permissions.request({ origins: [`https://${host}/*`] });
  if (granted) {
    await chrome.storage.session.remove("hostPermissionNeeded");
    render();
  }
});

render();
