import next from "eslint-config-next";
import coreWebVitals from "eslint-config-next/core-web-vitals";

/**
 * ESLint flat config.
 *
 * `next lint` was removed in Next 16, so `npm run lint` invokes ESLint directly.
 * `eslint-config-next@16` already exports flat-config arrays, so they are spread
 * in as-is — no `FlatCompat` bridge (which cannot serialise the plugin graph).
 */
const config = [
  {
    ignores: [".next/**", "node_modules/**", "next-env.d.ts"],
  },
  ...next,
  ...coreWebVitals,
];

export default config;
