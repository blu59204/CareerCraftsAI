export function ThemeScript({ zoneDefault }: { zoneDefault: "light" | "dark" }) {
  const code = `
    (function () {
      try {
        var saved = localStorage.getItem("theme");
        var chosen = saved === "light" || saved === "dark"
          ? saved
          : ${JSON.stringify(zoneDefault)};
        document.documentElement.classList.remove("light", "dark");
        document.documentElement.classList.add(chosen);
      } catch (_) {}
    })();
  `;
  return (
    <script
      id="theme-init"
      dangerouslySetInnerHTML={{ __html: code }}
    />
  );
}
