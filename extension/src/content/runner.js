// CareerCraft AI — runs one application task in this tab.
// Classic script — injected last, after dom.js, panel.js and drivers.js.
// Every network call goes through the background worker (chrome.runtime
// messages); this file only orchestrates the driver and reports outcomes.
(function () {
  if (window.__ccRunnerLoaded) return;
  window.__ccRunnerLoaded = true;

  const TERMINAL = new Set(["submitted", "failed", "cancelled"]);

  // Thrown when the server says the task is no longer active (cancelled
  // from the web app, expired, or claimed elsewhere): stop quietly.
  class StopTask extends Error {}

  let runningTaskId = null;

  function send(message) {
    return new Promise((resolve) => {
      try {
        chrome.runtime.sendMessage(message, (response) => {
          const lastError = chrome.runtime.lastError;
          resolve(response || { error: lastError ? lastError.message : "no_response" });
        });
      } catch (e) {
        // The extension was reloaded or updated under this page.
        resolve({ error: "extension_context_invalidated" });
      }
    });
  }

  function inactive(response) {
    return response && (response.active === false || response.status === 409 || (response.data && response.data.active === false));
  }

  function makeApi(task, state) {
    return {
      async event(stage, extra) {
        const response = await send({ type: "CC_EVENT", taskId: task.id, stage, ...(extra || {}) });
        if (TERMINAL.has(stage)) {
          state.finished = true;
          state.outcome = stage;
          return response;
        }
        if (inactive(response)) throw new StopTask("Task is no longer active");
        return response;
      },
      async plan(url, fields) {
        const response = await send({ type: "CC_PLAN", taskId: task.id, url, fields });
        if (inactive(response)) throw new StopTask("Task is no longer active");
        return response.data || null;
      },
      async resume() {
        const response = await send({ type: "CC_RESUME", taskId: task.id });
        return response.data || null;
      },
      async answer(label, value, questionKey) {
        const response = await send({ type: "CC_ANSWER", label, value, question_key: questionKey });
        return response.data || null;
      },
      async markSubmitting() {
        await send({ type: "CC_MARK_SUBMITTING", taskId: task.id });
      },
      async decide(stateText, questions) {
        const response = await send({ type: "CC_DECIDE", state: stateText, questions });
        return response.data || null;
      },
    };
  }

  const FINAL_MESSAGES = {
    submitted: "Application submitted. You can close this tab.",
    failed: "This application could not be completed — see CareerCraft for details.",
    cancelled: "Application cancelled.",
  };

  async function run(task, submitting) {
    const dom = window.CareerCraftDOM;
    const panel = window.CareerCraftPanel;
    const drivers = window.CareerCraftDrivers;
    const state = { finished: false, outcome: null };
    const api = makeApi(task, state);
    const ctx = { task, api, panel, delay: () => dom.delay(250, 800) };
    const subtitle = [task.company, task.role].filter(Boolean).join(" · ");

    panel.showStatus("Preparing your application…", subtitle);
    try {
      // Let client-rendered job pages (LinkedIn, Naukri) finish rendering.
      await dom.delay(1200, 1800);
      if (submitting) {
        await drivers.confirmAfterNavigation(ctx);
      } else {
        await drivers.select(task).run(ctx);
      }
      if (!state.finished) {
        await api.event("failed", { error: "The application flow ended without a result" });
      }
    } catch (e) {
      if (e instanceof StopTask) {
        panel.hide();
        return;
      }
      if (!state.finished) {
        const reason = (e && e.message ? e.message : String(e)).slice(0, 300);
        await api.event("failed", { error: `Unexpected page structure: ${reason}` });
      }
    }

    if (state.outcome === "submitted") {
      panel.showStatus(FINAL_MESSAGES.submitted, subtitle);
      setTimeout(() => panel.hide(), 6000);
    } else if (state.outcome) {
      panel.showStatus(FINAL_MESSAGES[state.outcome], subtitle);
      setTimeout(() => panel.hide(), 4000);
    } else {
      panel.hide();
    }
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (!message || message.type !== "RUN_TASK" || !message.task) return false;
    // One run per document: a duplicate "complete" event re-sends RUN_TASK.
    if (runningTaskId === message.task.id) {
      sendResponse({ ok: true, alreadyRunning: true });
      return false;
    }
    runningTaskId = message.task.id;
    sendResponse({ ok: true });
    run(message.task, !!message.submitting).finally(() => {
      runningTaskId = null;
    });
    return false;
  });
})();
