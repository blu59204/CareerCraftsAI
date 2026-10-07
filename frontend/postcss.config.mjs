// Tailwind directives (`@layer base` etc.) only exist in our own stylesheets.
// Third-party CSS that merely *uses* `@layer` (e.g. @copilotkit/react-core
// v2 styles) must skip the Tailwind plugin or PostCSS fails with
// "`@layer base` is used but no matching `@tailwind base` directive".
import path from "node:path";

const NODE_MODULES = `${path.sep}node_modules${path.sep}`;

const config = (ctx) => ({
  plugins: {
    tailwindcss: !ctx?.file || !ctx.file.includes(NODE_MODULES) ? {} : false,
    autoprefixer: {},
  },
});

export default config;
