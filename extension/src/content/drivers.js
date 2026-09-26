// CareerCraft AI — per-platform application drivers.
// Classic script — exposes window.CareerCraftDrivers. Depends on
// window.CareerCraftDOM and window.CareerCraftPanel (loaded first).
(function () {
  if (window.__ccDriversLoaded) return;
  window.__ccDriversLoaded = true;

  const dom = window.CareerCraftDOM;

  const CAPTCHA_SRC_RE = /recaptcha|hcaptcha|turnstile/i;
  const GENERIC_SUCCESS_RE =
    /application (has been |was )?(successfully )?submitted|thank you for applying|we have received your application|application received/i;
  const SUBMIT_TEXT_RE = /submit( your)? application|send application|submit|apply/i;
  const LINKEDIN_LOGIN_URL_RE = /login|authwall|checkpoint|uas/i;
  const LINKEDIN_SUBMIT_RE = /submit application/i;
  const LINKEDIN_NEXT_RE = /continue to next step|next|review your application|review/i;
  const LINKEDIN_CONFIRM_RE = /your application was sent|application sent|applied/i;
  const NAUKRI_LOGIN_RE = /\/nlogin/i;
  const NAUKRI_SUCCESS_RE = /successfully applied|applied to|application sent/i;

  // ── Small shared helpers ────────────────────────────────────────────────

  function waitFor(fn, timeoutMs, intervalMs) {
    intervalMs = intervalMs || 300;
    return new Promise((resolve) => {
      const start = Date.now();
      (function tick() {
        let value;
        try {
          value = fn();
        } catch (e) {
          value = null;
        }
        if (value) return resolve(value);
        if (Date.now() - start >= timeoutMs) return resolve(null);
        setTimeout(tick, intervalMs);
      })();
    });
  }

  // Only a challenge the user can see counts. Many application forms embed
  // an invisible reCAPTCHA (size=invisible) that never needs a person.
  function detectCaptchaFrame(root) {
    const frames = Array.from((root || document).querySelectorAll("iframe"));
    return frames.find((f) => {
      const src = f.getAttribute("src") || "";
      if (!CAPTCHA_SRC_RE.test(src) || /size=invisible/i.test(src)) return false;
      const rect = f.getBoundingClientRect();
      return dom.isVisible(f) && rect.width >= 60 && rect.height >= 40;
    });
  }

  // While a visible CAPTCHA is on the page, ask the user to solve it.
  // Returns true when the user cancelled (the caller must stop), false once
  // there is no CAPTCHA left and the flow can continue.
  async function guardCaptcha(ctx, root) {
    for (let round = 0; round < 5 && detectCaptchaFrame(root); round++) {
      const message = "Complete the CAPTCHA, then press Continue in the CareerCraft panel";
      await ctx.api.event("needs_input", { message });
      const res = await ctx.panel.showCaptcha({ company: ctx.task.company, role: ctx.task.role, message });
      if (res.action !== "continue") {
        await ctx.api.event("cancelled", { message: "Cancelled at the CAPTCHA" });
        return true;
      }
      await dom.delay(400, 600);
    }
    return false;
  }

  function isEmpty(value) {
    return value === null || value === undefined || value === "" || (Array.isArray(value) && value.length === 0);
  }

  // Required fields the plan could not answer and the user left empty.
  function missingRequired(planFields, typed) {
    return planFields.filter((f) => {
      if (!f.required || f.input_type === "file") return false;
      const value = typed && Object.prototype.hasOwnProperty.call(typed, f.field_id) ? typed[f.field_id] : f.value;
      return isEmpty(value);
    });
  }

  function buildOptionsMap(rawFields) {
    const map = {};
    const byName = {};
    for (const f of rawFields) {
      if (f.type === "select") map[f.id] = f.options;
      if ((f.type === "radio" || f.type === "checkbox") && f.name) {
        (byName[f.name] = byName[f.name] || []).push({ type: f.type, label: f.label });
      }
    }
    for (const [name, items] of Object.entries(byName)) {
      // A lone checkbox is a yes/no box, not a one-option group.
      if (items[0].type === "checkbox" && items.length === 1) continue;
      map[name] = items.map((item) => item.label);
    }
    return map;
  }

  function mergeFields(rawFields, plan, opts) {
    opts = opts || {};
    const fields = (plan.fields || []).map((f) => {
      if (f.input_type === "file" && f.value === "__resume__") {
        return { ...f, value: opts.resumeFilename ? `Resume: ${opts.resumeFilename}` : f.value };
      }
      return f;
    });
    return { fields, optionsByFieldId: buildOptionsMap(rawFields) };
  }

  async function applyOne(snap, fieldId, inputType, value) {
    const group = snap.byName.get(fieldId);
    if (group) {
      if (inputType === "radio") return dom.fillRadioGroup(group, value);
      if (group.length === 1 || typeof value === "boolean") return dom.fillSingleCheckbox(group[0].el, value);
      return dom.fillCheckboxGroup(group, value);
    }
    const el = snap.byId.get(fieldId);
    if (!el) return false;
    if (inputType === "select") return dom.fillSelect(el, value);
    if (inputType === "checkbox") return dom.fillSingleCheckbox(el, value);
    if (inputType === "radio") {
      if (!el.checked) dom.clickLike(el);
      return true;
    }
    return dom.fillText(el, value);
  }

  // Fills every planned field into the live DOM, pacing each fill. `typed`
  // (field_id -> value) overrides plan values for fields the user edited in
  // the panel. File inputs are skipped here — see attachResumeIfNeeded.
  async function applyPlan(ctx, snap, planFields, typed) {
    for (const field of planFields) {
      if (field.input_type === "file") continue;
      const hasOverride = typed && Object.prototype.hasOwnProperty.call(typed, field.field_id);
      const value = hasOverride ? typed[field.field_id] : field.value;
      if (value === null || value === undefined || value === "") continue;
      await ctx.delay();
      await applyOne(snap, field.field_id, field.input_type, value);
    }
  }

  async function attachResumeIfNeeded(ctx, snap, planFields) {
    const fileField = planFields.find((f) => f.input_type === "file" && f.value === "__resume__");
    if (!fileField) return null;
    const el = snap.byId.get(fileField.field_id);
    if (!el) return null;
    if (el.files && el.files.length > 0) return { filename: el.files[0].name };
    const resume = await ctx.api.resume();
    if (!resume) return null;
    await ctx.delay();
    const ok = await dom.attachFile(el, resume.base64, resume.filename, resume.mime);
    return ok ? { filename: resume.filename } : null;
  }

  async function rememberAnswers(ctx, fields, typed) {
    if (!typed) return;
    for (const field of fields) {
      if (!Object.prototype.hasOwnProperty.call(typed, field.field_id)) continue;
      const value = typed[field.field_id];
      if (isEmpty(value)) continue;
      // Consent boxes are ticked per application, never remembered.
      if (field.input_type === "checkbox" && typeof value === "boolean") continue;
      try {
        // No question_key: the server derives the canonical key from the
        // label, which is what makes the answer reusable on the next form.
        await ctx.api.answer(field.label || field.field_id, value);
      } catch (e) {
        /* best-effort — one bad save shouldn't stop the application */
      }
    }
  }

  function snippetAround(text, index, length) {
    const start = Math.max(0, index - 60);
    return text.slice(start, index + length + 60).trim();
  }

  // Polls the visible page text for `regex`; if nothing matches within
  // timeoutMs, falls back to asking the decision engine whether the page
  // confirms submission (a "noul" question over the first ~3000 chars).
  async function waitForConfirmation(ctx, regex, timeoutMs) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      const text = dom.visibleText(document, 4000);
      const match = regex.exec(text);
      if (match) return { confirmed: true, text: snippetAround(text, match.index, match[0].length) };
      await dom.delay(450, 550);
    }
    const text = dom.visibleText(document, 3000);
    const decision = await ctx.api.decide(text, {
      confirmed: { type: "noul", instructions: "Does this page confirm the job application was submitted?" },
    });
    const answer = decision && decision.answers && decision.answers.confirmed;
    const noul = answer && typeof answer.noul === "number" ? answer.noul : null;
    if (noul !== null) {
      if (noul >= 0.8) return { confirmed: true, text: text.slice(0, 300) };
      if (noul <= 0.2) return { confirmed: false, text: null };
    }
    return { confirmed: "unknown", text: null };
  }

  async function reportConfirmationResult(ctx, result, notConfirmedMessage) {
    if (result.confirmed === true) {
      await ctx.api.event("submitted", { confirmation_text: result.text || undefined, confirmation_url: location.href });
    } else if (result.confirmed === false) {
      await ctx.api.event("failed", { error: notConfirmedMessage });
    } else {
      await ctx.api.event("failed", {
        error: "Could not confirm whether the application was submitted — please check the site.",
      });
    }
  }

  // Lets the decision engine pick the advancing button when text heuristics
  // find nothing (state = visible button texts; act only if confidence >= .6).
  async function decideAdvanceButton(ctx, buttons) {
    if (!buttons.length) return null;
    const criteria = {};
    const texts = [];
    buttons.forEach((b, i) => {
      const key = "b" + i;
      const text = dom.textOf(b) || b.getAttribute("aria-label") || "button " + i;
      criteria[key] = text;
      texts.push(text);
    });
    let decision;
    try {
      decision = await ctx.api.decide(texts, {
        advance: {
          type: "choice",
          instructions: "Pick the button that advances this job application form to its next step, or submits it.",
          criteria,
        },
      });
    } catch (e) {
      return null;
    }
    const answer = decision && decision.answers && decision.answers.advance;
    if (!answer || typeof answer.confidence !== "number" || answer.confidence < 0.6) return null;
    const idx = Object.keys(criteria).indexOf(answer.choice);
    return idx >= 0 ? buttons[idx] : null;
  }

  function externalApplyError() {
    return "This job applies on the company site — open it from CareerCraft to apply there";
  }

  // ── Generic ATS driver (Greenhouse, Lever, Ashby, Workday, Indeed, …) ──

  function findSubmitControl(form) {
    let el = form.querySelector('button[type="submit"], input[type="submit"]');
    if (el) return el;
    const candidates = Array.from(form.querySelectorAll("button, input[type=button], a[role=button], a.button, a[class*=button]"));
    return candidates.find((c) => dom.isVisible(c) && (SUBMIT_TEXT_RE.test(dom.textOf(c)) || SUBMIT_TEXT_RE.test(c.value || "")));
  }

  function findApplicationForm() {
    const forms = Array.from(document.forms);
    if (!forms.length) return null;
    const scored = forms.map((f) => ({
      form: f,
      submit: findSubmitControl(f),
      inputs: f.querySelectorAll("input,select,textarea").length,
    }));
    const withSubmit = scored.filter((s) => s.submit);
    const pool = withSubmit.length ? withSubmit : scored;
    pool.sort((a, b) => b.inputs - a.inputs);
    return pool[0].inputs > 0 ? pool[0] : null;
  }

  const genericDriver = {
    async run(ctx) {
      if (await guardCaptcha(ctx)) return;

      const found = findApplicationForm();
      if (!found) throw new Error("Could not find an application form on this page");
      const { form, submit } = found;

      await ctx.api.event("filling", { message: "Filling the application" });
      const snap = dom.snapshot(form);
      const plan = await ctx.api.plan(location.href, snap.fields);
      if (!plan) throw new Error("Could not reach CareerCraft to plan this form");

      await applyPlan(ctx, snap, plan.fields);
      const resumeInfo = await attachResumeIfNeeded(ctx, snap, plan.fields);

      if (await guardCaptcha(ctx, form)) return;

      const merged = mergeFields(snap.fields, plan, { resumeFilename: resumeInfo && resumeInfo.filename });
      await ctx.api.event("review", { message: "Ready for your review" });
      let decision;
      let message;
      for (;;) {
        decision = await ctx.panel.showReview({
          company: ctx.task.company,
          role: ctx.task.role,
          message,
          fields: merged.fields,
          optionsByFieldId: merged.optionsByFieldId,
        });
        if (decision.action !== "submit") {
          await ctx.api.event("cancelled", { message: "Cancelled before submitting" });
          return;
        }
        const missing = missingRequired(plan.fields, decision.typed);
        if (!missing.length) break;
        message = "Answer the required questions first: " + missing.map((f) => f.label || f.field_id).join(", ");
      }
      await applyPlan(ctx, snap, plan.fields, decision.typed);
      if (decision.remember) await rememberAnswers(ctx, merged.fields, decision.typed);

      let submitEl = submit;
      if (!submitEl) {
        const buttons = Array.from(document.querySelectorAll("button, input[type=submit], input[type=button]")).filter((b) =>
          dom.isVisible(b)
        );
        submitEl = await decideAdvanceButton(ctx, buttons);
      }
      if (!submitEl) throw new Error("Could not find the submit control for this application");

      await ctx.delay();
      await ctx.api.markSubmitting();
      dom.clickLike(submitEl);

      const result = await waitForConfirmation(ctx, GENERIC_SUCCESS_RE, 15000);
      await reportConfirmationResult(ctx, result, "The page does not show a submission confirmation.");
    },
  };

  // ── LinkedIn Easy Apply driver ──────────────────────────────────────────

  function linkedinLooksSignedOut() {
    if (LINKEDIN_LOGIN_URL_RE.test(location.href)) return true;
    const hasNav = !!document.querySelector(".global-nav, #global-nav");
    const hasLoginForm = !!document.querySelector('form[action*="login"], #login-form, input[name="session_password"], input[name="session_key"]');
    return hasLoginForm && !hasNav;
  }

  function findEasyApplyButton() {
    let btn = document.querySelector("button.jobs-apply-button");
    if (btn && dom.isVisible(btn)) return btn;
    const all = Array.from(document.querySelectorAll("button"));
    return all.find((b) => dom.isVisible(b) && (/easy apply/i.test(dom.textOf(b)) || /easy apply/i.test(b.getAttribute("aria-label") || "")));
  }

  function findExternalApplyButton() {
    const all = Array.from(document.querySelectorAll("button, a"));
    return all.find((b) => dom.isVisible(b) && /^apply$/i.test(dom.textOf(b)) && !/easy apply/i.test(dom.textOf(b)));
  }

  function findModal() {
    return document.querySelector("[role='dialog'], .jobs-easy-apply-modal");
  }

  function findModalPrimaryButton(modal) {
    const buttons = Array.from(modal.querySelectorAll("button")).filter((b) => dom.isVisible(b) && !b.disabled);
    const submitBtn = buttons.find((b) => LINKEDIN_SUBMIT_RE.test(dom.textOf(b)));
    if (submitBtn) return { el: submitBtn, kind: "submit" };
    const nextBtn = buttons.find((b) => LINKEDIN_NEXT_RE.test(dom.textOf(b)));
    if (nextBtn) return { el: nextBtn, kind: "next" };
    return { el: null, kind: null, buttons };
  }

  function findInlineErrors(modal) {
    return Array.from(modal.querySelectorAll(".artdeco-inline-feedback--error, [aria-invalid='true']"));
  }

  const linkedinDriver = {
    async run(ctx) {
      for (let attempt = 0; attempt < 5 && linkedinLooksSignedOut(); attempt++) {
        await ctx.api.event("login_required", { message: "Sign in to LinkedIn in this tab, then press Continue." });
        const res = await ctx.panel.showLoginRequired({
          company: ctx.task.company,
          role: ctx.task.role,
          message: attempt === 0 ? "Sign in to LinkedIn in this tab, then press Continue." : "Still signed out — finish signing in, then press Continue.",
        });
        if (res.action !== "continue") {
          await ctx.api.event("cancelled", { message: "Cancelled while signing in" });
          return;
        }
      }
      if (linkedinLooksSignedOut()) {
        throw new Error("Could not detect a signed-in LinkedIn session");
      }

      if (await guardCaptcha(ctx)) return;

      const easyApply = findEasyApplyButton();
      if (!easyApply) {
        if (findExternalApplyButton()) {
          await ctx.api.event("failed", { error: externalApplyError() });
          return;
        }
        throw new Error("Could not find the Easy Apply button on this job page");
      }

      await ctx.api.event("filling", { message: "Opening Easy Apply" });
      await ctx.delay();
      dom.clickLike(easyApply);
      const modal = await waitFor(findModal, 8000);
      if (!modal) throw new Error("The Easy Apply modal did not open");

      for (let step = 0; step < 15; step++) {
        const m = findModal();
        if (!m) throw new Error("The Easy Apply modal closed unexpectedly");

        if (await guardCaptcha(ctx, m)) return;

        const snap = dom.snapshot(m);
        const plan = await ctx.api.plan(location.href, snap.fields);
        if (!plan) throw new Error("Could not reach CareerCraft to plan this step");
        await applyPlan(ctx, snap, plan.fields);
        const resumeInfo = await attachResumeIfNeeded(ctx, snap, plan.fields);
        const merged = mergeFields(snap.fields, plan, { resumeFilename: resumeInfo && resumeInfo.filename });

        if (plan.unresolved_required.length) {
          await ctx.api.event("needs_input", { message: "A few required questions need your answer." });
          const res = await ctx.panel.showNeedsInput({
            company: ctx.task.company,
            role: ctx.task.role,
            fields: merged.fields.filter((f) => plan.unresolved_required.includes(f.field_id) || f.requires_review),
            optionsByFieldId: merged.optionsByFieldId,
          });
          if (res.action !== "continue") {
            await ctx.api.event("cancelled", { message: "Cancelled by user" });
            return;
          }
          await applyPlan(ctx, snap, plan.fields, res.typed);
          if (res.remember) await rememberAnswers(ctx, merged.fields, res.typed);
        }

        let primary = findModalPrimaryButton(m);
        if (!primary.el) {
          const chosen = await decideAdvanceButton(ctx, primary.buttons || []);
          if (chosen) primary = { el: chosen, kind: LINKEDIN_SUBMIT_RE.test(dom.textOf(chosen)) ? "submit" : "next" };
        }
        if (!primary.el) throw new Error("Could not find a button to advance the Easy Apply modal");

        if (primary.kind === "submit") {
          await ctx.api.event("review", { message: "Ready for your review" });
          const decision = await ctx.panel.showReview({
            company: ctx.task.company,
            role: ctx.task.role,
            fields: merged.fields,
            optionsByFieldId: merged.optionsByFieldId,
          });
          if (decision.action !== "submit") {
            await ctx.api.event("cancelled", { message: "Cancelled before submitting" });
            return;
          }
          await applyPlan(ctx, snap, plan.fields, decision.typed);
          if (decision.remember) await rememberAnswers(ctx, merged.fields, decision.typed);

          await ctx.delay();
          await ctx.api.markSubmitting();
          dom.clickLike(primary.el);
          const result = await waitForConfirmation(ctx, LINKEDIN_CONFIRM_RE, 20000);
          await reportConfirmationResult(ctx, result, "LinkedIn did not show a submission confirmation.");
          return;
        }

        await ctx.delay();
        dom.clickLike(primary.el);
        await dom.delay(700, 900);

        const afterModal = findModal();
        if (afterModal && findInlineErrors(afterModal).length) {
          await ctx.api.event("needs_input", { message: "LinkedIn flagged some answers — fix them, then press Continue." });
          const res = await ctx.panel.showNeedsInput({
            company: ctx.task.company,
            role: ctx.task.role,
            message: "LinkedIn flagged some answers — fix them in the form, then press Continue.",
            fields: [],
            optionsByFieldId: {},
          });
          if (res.action !== "continue") {
            await ctx.api.event("cancelled", { message: "Cancelled by user" });
            return;
          }
        }
      }
      throw new Error("Easy Apply had too many steps");
    },
  };

  // ── Naukri driver ───────────────────────────────────────────────────────

  function naukriLooksSignedOut() {
    if (NAUKRI_LOGIN_RE.test(location.href)) return true;
    return !!document.querySelector("#login_Layer, .login-modal, [class*='loginModal' i]");
  }

  function findNaukriApplyButton() {
    let btn = document.getElementById("apply-button");
    if (btn && dom.isVisible(btn)) return btn;
    const all = Array.from(document.querySelectorAll("button, a"));
    return all.find((b) => dom.isVisible(b) && /^apply$/i.test(dom.textOf(b)));
  }

  function findNaukriExternalApply() {
    const all = Array.from(document.querySelectorAll("button, a"));
    return all.find((b) => dom.isVisible(b) && /apply on company site/i.test(dom.textOf(b)));
  }

  function findChatbotDrawer() {
    const all = Array.from(document.querySelectorAll("div, section, aside"));
    return all.find((el) => /chatbot|drawer/i.test(el.className || "") && dom.isVisible(el));
  }

  function findDrawerAdvanceButton(drawer) {
    const buttons = Array.from(drawer.querySelectorAll("button")).filter((b) => dom.isVisible(b) && !b.disabled);
    return buttons.find((b) => /save|submit|next|send/i.test(dom.textOf(b))) || buttons[buttons.length - 1];
  }

  async function handleChatbotDrawer(ctx) {
    for (let step = 0; step < 10; step++) {
      if (NAUKRI_SUCCESS_RE.test(dom.visibleText(document, 3000))) return;
      const drawer = findChatbotDrawer();
      if (!drawer) return;
      if (await guardCaptcha(ctx, drawer)) return "cancelled";

      const snap = dom.snapshot(drawer);
      if (snap.fields.length === 0) {
        const questionText = dom.textOf(drawer).slice(0, 300) || "Answer the chatbot question in the page, then press Continue.";
        await ctx.api.event("needs_input", { message: "Answer the Naukri chatbot question, then press Continue." });
        const res = await ctx.panel.showNeedsInput({
          company: ctx.task.company,
          role: ctx.task.role,
          message: questionText,
          fields: [],
          optionsByFieldId: {},
        });
        if (res.action !== "continue") {
          await ctx.api.event("cancelled", { message: "Cancelled at the chatbot" });
          return "cancelled";
        }
        await dom.delay(400, 600);
        continue;
      }

      const plan = await ctx.api.plan(location.href, snap.fields);
      if (!plan) throw new Error("Could not reach CareerCraft to plan the chatbot question");
      await applyPlan(ctx, snap, plan.fields);

      if (plan.unresolved_required.length) {
        const merged = mergeFields(snap.fields, plan);
        await ctx.api.event("needs_input", { message: "A question needs your answer." });
        const res = await ctx.panel.showNeedsInput({
          company: ctx.task.company,
          role: ctx.task.role,
          fields: merged.fields,
          optionsByFieldId: merged.optionsByFieldId,
        });
        if (res.action !== "continue") {
          await ctx.api.event("cancelled", { message: "Cancelled at the chatbot" });
          return "cancelled";
        }
        await applyPlan(ctx, snap, plan.fields, res.typed);
        if (res.remember) await rememberAnswers(ctx, merged.fields, res.typed);
      }

      const advance = findDrawerAdvanceButton(drawer);
      if (advance) {
        await ctx.delay();
        dom.clickLike(advance);
      }
      await dom.delay(600, 800);
    }
  }

  const naukriDriver = {
    async run(ctx) {
      for (let attempt = 0; attempt < 5 && naukriLooksSignedOut(); attempt++) {
        await ctx.api.event("login_required", { message: "Sign in to Naukri in this tab, then press Continue." });
        const res = await ctx.panel.showLoginRequired({
          company: ctx.task.company,
          role: ctx.task.role,
          message: attempt === 0 ? "Sign in to Naukri in this tab, then press Continue." : "Still signed out — finish signing in, then press Continue.",
        });
        if (res.action !== "continue") {
          await ctx.api.event("cancelled", { message: "Cancelled while signing in" });
          return;
        }
      }
      if (naukriLooksSignedOut()) throw new Error("Could not detect a signed-in Naukri session");

      if (await guardCaptcha(ctx)) return;

      if (findNaukriExternalApply() && !findNaukriApplyButton()) {
        await ctx.api.event("failed", { error: externalApplyError() });
        return;
      }
      const applyBtn = findNaukriApplyButton();
      if (!applyBtn) throw new Error("Could not find the Apply button on this Naukri page");
      if (/company site/i.test(dom.textOf(applyBtn))) {
        await ctx.api.event("failed", { error: externalApplyError() });
        return;
      }

      // Naukri's own Apply button submits immediately — the review panel
      // must appear *before* we click it, never after.
      await ctx.api.event("review", { message: "Ready to apply on Naukri" });
      const decision = await ctx.panel.showReview({
        company: ctx.task.company,
        role: ctx.task.role,
        message: "Naukri applies with your Naukri profile — submit?",
        fields: [],
        optionsByFieldId: {},
      });
      if (decision.action !== "submit") {
        await ctx.api.event("cancelled", { message: "Cancelled before applying" });
        return;
      }

      await ctx.delay();
      await ctx.api.markSubmitting();
      dom.clickLike(applyBtn);

      await dom.delay(900, 1200);
      if (await guardCaptcha(ctx)) return;
      if ((await handleChatbotDrawer(ctx)) === "cancelled") return;

      const result = await waitForConfirmation(ctx, NAUKRI_SUCCESS_RE, 15000);
      await reportConfirmationResult(ctx, result, "Naukri did not show a submission confirmation.");
    },
  };

  // ── Selection ────────────────────────────────────────────────────────────

  function select(task) {
    const platform = (task && task.platform) || "";
    if (platform === "linkedin" || /(^|\.)linkedin\.com$/.test(location.hostname)) return linkedinDriver;
    if (platform === "naukri" || /naukri\.com$/.test(location.hostname)) return naukriDriver;
    return genericDriver;
  }

  // The submit click navigated to a new page (common on ATS forms): the
  // re-injected runner only has to read the outcome, never fill again.
  async function confirmAfterNavigation(ctx) {
    const platform = (ctx.task && ctx.task.platform) || "";
    const regex =
      platform === "linkedin" ? LINKEDIN_CONFIRM_RE : platform === "naukri" ? NAUKRI_SUCCESS_RE : GENERIC_SUCCESS_RE;
    const result = await waitForConfirmation(ctx, regex, 15000);
    await reportConfirmationResult(ctx, result, "The page after submitting does not show a confirmation.");
  }

  window.CareerCraftDrivers = { select, confirmAfterNavigation, genericDriver, linkedinDriver, naukriDriver };
})();
