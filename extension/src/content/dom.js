// CareerCraft AI — DOM utilities shared by every driver.
// Classic script (not a module) — exposes window.CareerCraftDOM.
// Guarded against double-injection: re-running this file on the same
// document (e.g. a duplicate "complete" event) is a safe no-op.
(function () {
  if (window.__ccDomLoaded) return;
  window.__ccDomLoaded = true;

  const FIELD_ATTR = "data-cc-field";

  function textOf(node) {
    if (!node) return "";
    const t = "innerText" in node ? node.innerText : node.textContent;
    return (t || "").replace(/\s+/g, " ").trim();
  }

  function isVisible(el) {
    if (!el) return false;
    if (el.closest("[hidden]")) return false;
    let style;
    try {
      style = window.getComputedStyle(el);
    } catch (e) {
      return false;
    }
    if (!style) return false;
    if (style.display === "none" || style.visibility === "hidden") return false;
    if (parseFloat(style.opacity || "1") === 0) return false;
    return el.getClientRects().length > 0;
  }

  function nextFieldId() {
    if (typeof window.__ccFieldCounter !== "number") window.__ccFieldCounter = 0;
    window.__ccFieldCounter += 1;
    return "cc-" + window.__ccFieldCounter;
  }

  function ensureId(el) {
    if (el.id) return el.id;
    let existing = el.getAttribute(FIELD_ATTR);
    if (!existing) {
      existing = nextFieldId();
      el.setAttribute(FIELD_ATTR, existing);
    }
    return existing;
  }

  // el.labels?.[0]?.innerText || aria-label || aria-labelledby text ||
  // (structural fallback, useful on LinkedIn's custom markup) || placeholder || name
  function getLabel(el) {
    let text = "";
    try {
      if (el.labels && el.labels[0]) text = textOf(el.labels[0]);
    } catch (e) {
      /* labels not supported on this element type */
    }
    if (!text) text = (el.getAttribute("aria-label") || "").trim();
    if (!text) {
      const labelledBy = el.getAttribute("aria-labelledby");
      if (labelledBy) {
        text = labelledBy
          .split(/\s+/)
          .map((id) => textOf(document.getElementById(id)))
          .filter(Boolean)
          .join(" ")
          .trim();
      }
    }
    if (!text) {
      // Nearest label / legend / span[aria-hidden=true] inside the field's
      // container — LinkedIn rarely uses a real <label for="…">.
      const container =
        el.closest("[class*='form-element'], [class*='fb-'], li, fieldset, div") || el.parentElement;
      if (container) {
        const candidate = container.querySelector("label, legend, span[aria-hidden='true']");
        if (candidate && candidate !== el && !candidate.contains(el)) {
          text = textOf(candidate);
        }
      }
    }
    if (!text) text = (el.getAttribute("placeholder") || "").trim();
    if (!text) text = el.name || "";
    return text.trim();
  }

  function getGroupLabel(el) {
    const fieldset = el.closest("fieldset");
    if (fieldset) {
      const legend = fieldset.querySelector("legend");
      if (legend) {
        const t = textOf(legend);
        if (t) return t;
      }
      const aria = (fieldset.getAttribute("aria-label") || "").trim();
      if (aria) return aria;
    }
    const group = el.closest("[role='radiogroup'], [role='group']");
    if (group) {
      const aria = (group.getAttribute("aria-label") || "").trim();
      if (aria) return aria;
      const labelledBy = group.getAttribute("aria-labelledby");
      if (labelledBy) {
        const t = labelledBy
          .split(/\s+/)
          .map((id) => textOf(document.getElementById(id)))
          .filter(Boolean)
          .join(" ")
          .trim();
        if (t) return t;
      }
    }
    return "";
  }

  function inputTypeOf(el) {
    const tag = el.tagName.toLowerCase();
    if (tag === "select") return "select";
    if (tag === "textarea") return "textarea";
    return (el.type || "text").toLowerCase();
  }

  function currentValue(el, type) {
    if (type === "select") {
      if (!el.value) return "";
      const opt = el.selectedOptions && el.selectedOptions[0];
      return opt ? opt.text.trim() : "";
    }
    if (type === "file") {
      return Array.from(el.files || [])
        .map((f) => f.name)
        .join(",");
    }
    if (type === "checkbox" || type === "radio") return el.value;
    return el.value || "";
  }

  // Snapshot every fillable field under `root` (document by default),
  // skipping password/hidden inputs. Returns { fields, byId, byName } where
  // byId/byName let a driver find the live elements again after planning.
  function snapshot(root) {
    root = root || document;
    const nodes = Array.from(root.querySelectorAll("input,select,textarea")).filter(
      (e) => e.type !== "password" && e.type !== "hidden"
    );
    const fields = [];
    const byId = new Map();
    const byName = new Map();

    for (const el of nodes) {
      const type = inputTypeOf(el);
      const id = ensureId(el);
      const label = getLabel(el);
      const group_label = type === "radio" || type === "checkbox" ? getGroupLabel(el) : "";
      const options = type === "select" ? Array.from(el.options).map((o) => o.text.trim()).filter(Boolean) : [];
      const visible = isVisible(el);
      const disabled = !!el.disabled;

      fields.push({
        name: el.name || "",
        id,
        type,
        label,
        group_label,
        value: currentValue(el, type),
        checked: !!el.checked,
        required: !!el.required,
        options,
        visible,
        disabled,
      });

      byId.set(id, el);
      if ((type === "radio" || type === "checkbox") && el.name) {
        if (!byName.has(el.name)) byName.set(el.name, []);
        byName.get(el.name).push({ el, label });
      }
    }

    return { fields, byId, byName };
  }

  function setNativeValue(el, value) {
    const proto = el.tagName === "TEXTAREA" ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
    const descriptor = Object.getOwnPropertyDescriptor(proto, "value");
    if (descriptor && descriptor.set) {
      descriptor.set.call(el, value);
    } else {
      el.value = value;
    }
  }

  function setNativeSelectValue(el, optionValue) {
    const descriptor = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, "value");
    if (descriptor && descriptor.set) {
      descriptor.set.call(el, optionValue);
    } else {
      el.value = optionValue;
    }
  }

  function fireEvents(el, types) {
    for (const type of types) {
      el.dispatchEvent(new Event(type, { bubbles: true }));
    }
  }

  function normalize(s) {
    return (s || "").toString().trim().toLowerCase();
  }

  function findOption(options, text) {
    const target = normalize(text);
    return options.find((o) => normalize(o.text) === target) || options.find((o) => normalize(o.text).includes(target));
  }

  async function fillText(el, value) {
    el.focus();
    setNativeValue(el, value);
    fireEvents(el, ["input", "change"]);
    el.blur();
    fireEvents(el, ["blur"]);
  }

  async function fillSelect(el, text) {
    const options = Array.from(el.options);
    const match = findOption(options, text);
    if (!match) return false;
    el.focus();
    setNativeSelectValue(el, match.value);
    fireEvents(el, ["input", "change"]);
    el.blur();
    return true;
  }

  function clickLike(el) {
    el.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
    el.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, cancelable: true }));
    el.click();
  }

  async function fillRadioGroup(elements, text) {
    const target = normalize(text);
    const match =
      elements.find((e) => normalize(e.label) === target) ||
      elements.find((e) => normalize(e.label).includes(target));
    if (!match) return false;
    if (!match.el.checked) clickLike(match.el);
    return true;
  }

  async function fillCheckboxGroup(elements, values) {
    const wanted = new Set((Array.isArray(values) ? values : [values]).map(normalize));
    for (const { el, label } of elements) {
      const shouldCheck = wanted.has(normalize(label));
      if (!!el.checked !== shouldCheck) clickLike(el);
    }
    return true;
  }

  async function fillSingleCheckbox(el, value) {
    const shouldCheck = value === true || normalize(value) === "true" || normalize(value) === "yes";
    if (!!el.checked !== shouldCheck) clickLike(el);
    return true;
  }

  function base64ToBytes(base64) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return bytes;
  }

  async function attachFile(el, base64, filename, mime) {
    const bytes = base64ToBytes(base64);
    const file = new File([bytes], filename || "resume.pdf", { type: mime || "application/pdf" });
    const dt = new DataTransfer();
    dt.items.add(file);
    el.files = dt.files;
    fireEvents(el, ["input", "change"]);
    return el.files && el.files.length === 1;
  }

  function delay(min, max) {
    min = typeof min === "number" ? min : 250;
    max = typeof max === "number" ? max : 800;
    const ms = min + Math.random() * (max - min);
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function findByText(root, selector, regex) {
    const nodes = Array.from(root.querySelectorAll(selector));
    return nodes.find((n) => regex.test(textOf(n)) || regex.test(n.getAttribute("aria-label") || ""));
  }

  function visibleText(root, limit) {
    const text = textOf(root && root.body ? root.body : root || document.body);
    return limit ? text.slice(0, limit) : text;
  }

  window.CareerCraftDOM = {
    isVisible,
    getLabel,
    getGroupLabel,
    snapshot,
    setNativeValue,
    fillText,
    fillSelect,
    fillRadioGroup,
    fillCheckboxGroup,
    fillSingleCheckbox,
    attachFile,
    delay,
    clickLike,
    findByText,
    textOf,
    normalize,
    visibleText,
  };
})();
