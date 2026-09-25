/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The typed API client runs server-side (React Server Components), so the
  // browser never calls the SmartESS API directly. This is deliberate: the
  // backend has no CORS middleware today (design.md §10.4) and the LLM API key
  // must never reach the browser (design.md §15.1, UX.md §31).
  env: {},
};

export default nextConfig;
