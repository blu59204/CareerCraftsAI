import Script from "next/script";

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
    <Script id="theme-init" strategy="beforeInteractive">
      {code}
    </Script>
  );
}
