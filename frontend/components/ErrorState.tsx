import { STATE_COPY } from "@/lib/copy/states";
import type { ApiResult } from "@/lib/api/client";

/**
 * ErrorState — a failed request, without destroying already-loaded context
 * (UX.md §30 "System error", §31; design.md §14.15).
 *
 * The backend's own `detail` is shown verbatim in monospace, because it is often
 * the only signal distinguishing an auth failure from a rate limit
 * (design.md §14.8). Red is used here legitimately: `--ss-state-reject` is
 * reserved for system failure and validation rejection (UX.md §44.3).
 */
export function ErrorState({ result }: { result: ApiResult<unknown> }) {
  if (result.kind === "ok") return null;

  const copy =
    result.kind === "not-implemented"
      ? STATE_COPY.CAPABILITY_NOT_IMPLEMENTED
      : STATE_COPY.SYSTEM_ERROR;

  // A missing capability is not an error condition; it is an unimplemented one.
  const isCapability = result.kind === "not-implemented";
  const borderColor = isCapability
    ? "var(--ss-border-strong)"
    : "var(--ss-state-reject)";

  const detail =
    result.kind === "not-implemented"
      ? `${result.endpoint} — ${result.reference}`
      : result.kind === "not-found"
        ? `404 ${result.endpoint} — ${result.detail}`
        : result.kind === "unreachable"
          ? `${result.endpoint} — API unreachable: ${result.detail}`
          : `${result.status} ${result.endpoint} — ${result.detail}`;

  return (
    <div
      className={`flex flex-col gap-[var(--ss-space-2)] border p-[var(--ss-space-4)] ${
        isCapability ? "border-dashed" : ""
      }`}
      style={{ borderColor, borderRadius: "var(--ss-radius-sm)" }}
      data-state={isCapability ? "CAPABILITY_NOT_IMPLEMENTED" : "SYSTEM_ERROR"}
      role={isCapability ? undefined : "alert"}
    >
      <span
        className="ss-field-label"
        style={{ color: isCapability ? "var(--ss-text-secondary)" : "var(--ss-state-reject)" }}
      >
        {copy.title}
      </span>
      <p className="text-[var(--ss-text-secondary)]" style={{ maxWidth: "var(--ss-measure-prose)" }}>
        {copy.body}
      </p>
      <code className="ss-mono break-all text-[var(--ss-text-muted)]">{detail}</code>
    </div>
  );
}
