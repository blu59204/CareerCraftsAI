import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

const require = createRequire(import.meta.url);
function load(relativePath, overrides, globals = {}) {
  const source = readFileSync(new URL(relativePath, import.meta.url), "utf8");
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const module = { exports: {} };
  vm.runInNewContext(code, { module, exports: module.exports, require: (name) => overrides[name] ?? require(name), ...globals });
  return module.exports;
}

test("fifteen switch clicks alternate the provider theme without a second checked state", () => {
  let theme = "light";
  const { default: ThemeSwitch } = load("../ui/theme-switch.tsx", {
    react: { useState: () => [true], useEffect: () => {} },
    "@/components/theme/ThemeProvider": { useTheme: () => ({ theme, setTheme: (next) => { theme = next; } }) },
    "@/components/ui/switch": { Switch: "switch" },
    "@/lib/utils": { cn: (...values) => values.filter(Boolean).join(" ") },
  });
  for (let click = 0; click < 15; click++) {
    const control = ThemeSwitch({}).props.children[0];
    assert.equal(control.props["aria-label"], "Dark mode");
    assert.equal(control.props.checked, theme === "dark");
    control.props.onCheckedChange(!control.props.checked);
    assert.equal(theme, click % 2 === 0 ? "dark" : "light");
  }
});

test("mount preserves saved preference and rapid toggles use state while the DOM lags", () => {
  const state = [];
  let cursor = 0;
  let effects = [];
  let saved = "light";
  const writes = [];
  const { ThemeProvider } = load("./ThemeProvider.tsx", {
    react: {
      createContext: () => ({ Provider: "provider" }),
      useState: (initial) => {
        const index = cursor++;
        if (!(index in state)) state[index] = initial;
        return [state[index], (next) => { state[index] = typeof next === "function" ? next(state[index]) : next; }];
      },
      useEffect: (callback) => effects.push(callback),
      useCallback: (callback) => callback,
      useMemo: (callback) => callback(),
    },
  }, {
    window: { localStorage: { getItem: () => saved, setItem: (_, value) => { writes.push(value); saved = value; } } },
    document: { documentElement: { classList: { remove() {}, add() {}, contains: () => true } } },
  });
  const render = () => {
    cursor = 0;
    effects = [];
    return ThemeProvider({ zoneDefault: "dark", children: null }).props.value;
  };
  render();
  effects.forEach((effect) => effect());
  assert.equal(saved, "light");
  assert.deepEqual(writes, []);
  const value = render();
  assert.equal(value.theme, "light");
  value.toggleTheme();
  assert.equal(state[0], "dark");
  value.toggleTheme();
  assert.equal(state[0], "light");
  value.toggleTheme();
  assert.equal(state[0], "dark");
});
