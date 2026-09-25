/**
 * Typed API client for the SmartESS backend.
 *
 * Rules this module enforces (UX.md §43.2, §35 Rule 1; design.md §4):
 *
 *  1. Plain `fetch`. No Redux, Zustand, TanStack Query, SWR, or any other
 *     global-state / data-fetching abstraction.
 *  2. Server-side only. Calls originate in React Server Components so the
 *     browser never talks to the API directly — the backend has no CORS
 *     middleware (design.md §10.4) and the LLM API key must never reach the
 *     browser (design.md §15.1).
 *  3. Never fabricate a response. A missing endpoint yields a typed
 *     `ApiUnavailable`, which the UI renders as an explicit readiness state.
 *  4. No engineering calculation. This layer transports values; it does not
 *     derive them (UX.md §35 Rule 2).
 */

const DEFAULT_BASE_URL = "http://127.0.0.1:8000";
const DEFAULT_TIMEOUT_MS = 10_000;

/** Runtime lookup. A static `process.env.NAME` access is inlined at build time. */
function envValue(name: string): string | undefined {
  const value = process.env[name];
  return value && value.length > 0 ? value : undefined;
}

function baseUrl(): string | null {
  const configured = envValue("SMARTESS_API_BASE_URL")?.replace(/\/+$/, "");
  if (configured) return configured;
  // Same-host development only. Production must name its API explicitly so a
  // split deploy cannot silently call loopback.
  if (process.env.NODE_ENV === "production") return null;
  return DEFAULT_BASE_URL;
}

function timeoutMs(): number {
  const raw = envValue("SMARTESS_API_TIMEOUT_MS");
  if (!raw) return DEFAULT_TIMEOUT_MS;
  const parsed = Number.parseInt(raw, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_TIMEOUT_MS;
}

/* ── result type ───────────────────────────────────────────────────────── */

/**
 * Why this is a result type rather than thrown errors: the UI must distinguish
 * NO DATA from NOT IMPLEMENTED from SYSTEM ERROR (UX.md §30, design.md §14.16).
 * Collapsing them into one thrown Error would make that impossible.
 */
export type ApiResult<T> =
  | { readonly kind: "ok"; readonly data: T }
  /** Endpoint does not exist in this backend yet (design.md §10.2). */
  | { readonly kind: "not-implemented"; readonly endpoint: string; readonly reference: string }
  /** Reached the API; it reported the resource absent. */
  | { readonly kind: "not-found"; readonly endpoint: string; readonly detail: string }
  /** Could not reach the API at all. */
  | { readonly kind: "unreachable"; readonly endpoint: string; readonly detail: string }
  /** Reached the API; it failed. `detail` is the backend's own message, verbatim. */
  | { readonly kind: "error"; readonly endpoint: string; readonly status: number; readonly detail: string };

export function isOk<T>(r: ApiResult<T>): r is { kind: "ok"; data: T } {
  return r.kind === "ok";
}

/* ── core request ──────────────────────────────────────────────────────── */

interface RequestOptions {
  readonly method?: "GET" | "POST";
  readonly body?: unknown;
  /** Investigation artifacts are immutable once written, but the list grows. */
  readonly revalidateSeconds?: number;
  /**
   * Per-request override. `POST /investigations` is synchronous and runs the
   * whole LangGraph pipeline including LLM calls, so it needs far longer than
   * the default (design.md §19.10).
   */
  readonly timeoutMs?: number;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<ApiResult<T>> {
  const endpoint = `${options.method ?? "GET"} ${path}`;
  const root = baseUrl();
  if (!root) {
    return {
      kind: "unreachable",
      endpoint,
      detail: "SMARTESS_API_BASE_URL is not set. Production does not assume a loopback API.",
    };
  }
  const url = `${root}${path}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.timeoutMs ?? timeoutMs());

  try {
    const response = await fetch(url, {
      method: options.method ?? "GET",
      headers: options.body ? { "content-type": "application/json" } : undefined,
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
      cache: options.revalidateSeconds === undefined ? "no-store" : undefined,
      next: options.revalidateSeconds === undefined ? undefined : { revalidate: options.revalidateSeconds },
    });

    if (response.status === 404) {
      return { kind: "not-found", endpoint, detail: await readDetail(response) };
    }
    if (!response.ok) {
      return {
        kind: "error",
        endpoint,
        status: response.status,
        detail: await readDetail(response),
      };
    }
    return { kind: "ok", data: (await response.json()) as T };
  } catch (cause) {
    return {
      kind: "unreachable",
      endpoint,
      detail: cause instanceof Error ? cause.message : String(cause),
    };
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Reads FastAPI's `{detail}` envelope. The message is surfaced verbatim because
 * it is often the only signal distinguishing, say, an auth failure from a rate
 * limit (design.md §14.8).
 */
async function readDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
    return JSON.stringify(body);
  } catch {
    return `${response.status} ${response.statusText}`;
  }
}

export const api = { request };

/* ── endpoints that DO NOT exist yet ───────────────────────────────────── */

/**
 * Declares an endpoint required by design.md §10.2 that the backend does not
 * implement. Returning this — rather than inventing a shape — is what keeps the
 * module, telemetry, anomaly, evaluation, evidence, corpus and provenance
 * surfaces in an honest readiness state.
 */
export function notImplemented<T>(endpoint: string, reference: string): ApiResult<T> {
  return { kind: "not-implemented", endpoint, reference };
}
