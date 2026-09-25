import { StatusChip } from "@/components/StatusChip";
import { EmptyState } from "@/components/EmptyState";

/**
 * ReadinessPanel — the Pipeline Readiness table (UX.md §30 "Missing artifacts";
 * design.md §14.1).
 *
 * This is a SETUP state, not a generic error. Every artifact is listed with its
 * expected path and the CLI that produces it, so a fresh clone — which has none
 * of the gitignored `ml/datasets/` artifacts (design.md §11.4) — tells the
 * engineer exactly what to run.
 *
 * Status is `UNKNOWN` for every row until `GET /readiness` exists
 * (design.md §10.4). It is never guessed.
 */
export interface ReadinessRow {
  readonly artifact: string;
  /** `PRESENT` | `ABSENT` | `READY` | `NOT_CONFIGURED` | `UNKNOWN` */
  readonly status: string;
  readonly path: string;
  readonly cli: string;
}

/**
 * Artifact inventory taken from design.md §11.1 and §14.1. Paths and CLIs are
 * real; statuses are not fabricated.
 */
export const REQUIRED_ARTIFACTS: readonly Omit<ReadinessRow, "status">[] = [
  {
    artifact: "features",
    path: "ml/datasets/features/v1/observation-features.parquet",
    cli: "scripts/build_features.py",
  },
  {
    artifact: "scores",
    path: "ml/datasets/scores/<model_id>/observation-scores.parquet",
    cli: "scripts/train_anomaly_model.py",
  },
  {
    artifact: "evaluation",
    path: "ml/datasets/evaluation/<model_id>/evaluation-summary.json",
    cli: "scripts/evaluate_anomaly.py",
  },
  {
    artifact: "model",
    path: "ml/models/<model_id>/model-record.json",
    cli: "scripts/train_anomaly_model.py",
  },
  {
    artifact: "healthy reference",
    path: "ml/datasets/investigations/reference/healthy-reference.json",
    cli: "scripts/build_healthy_reference.py",
  },
  {
    artifact: "knowledge base",
    path: "knowledge_base/chroma (collection: evidence)",
    cli: "scripts/ingest_knowledge.py",
  },
  {
    artifact: "LLM",
    path: "LLM_PROVIDER / LLM_MODEL / LLM_API_KEY",
    cli: "scripts/check_llm.py",
  },
];

export function ReadinessPanel({
  rows,
  unavailableReason,
}: {
  rows?: readonly ReadinessRow[];
  /** Set when `GET /readiness` does not exist, so status cannot be determined. */
  unavailableReason?: string;
}) {
  const data: readonly ReadinessRow[] =
    rows ?? REQUIRED_ARTIFACTS.map((a) => ({ ...a, status: "UNKNOWN" }));

  return (
    <div className="flex flex-col gap-[var(--ss-space-3)] p-[var(--ss-space-4)]">
      {unavailableReason && (
        <EmptyState
          state="CAPABILITY_NOT_IMPLEMENTED"
          body="Artifact presence cannot be determined: the readiness endpoint does not exist. The inventory below lists what each surface requires."
          detail={unavailableReason}
        />
      )}

      <table className="w-full border-collapse text-left">
        <caption className="ss-sr-only">
          Pipeline readiness: required SmartESS artifacts, their status, expected
          path and producing command.
        </caption>
        <thead>
          <tr className="border-b border-[var(--ss-border-strong)]">
            <th scope="col" className="ss-field-label py-[var(--ss-space-2)] pr-[var(--ss-space-4)]">
              Artifact
            </th>
            <th scope="col" className="ss-field-label py-[var(--ss-space-2)] pr-[var(--ss-space-4)]">
              Status
            </th>
            <th scope="col" className="ss-field-label py-[var(--ss-space-2)] pr-[var(--ss-space-4)]">
              Expected path
            </th>
            <th scope="col" className="ss-field-label py-[var(--ss-space-2)]">
              Produced by
            </th>
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr key={row.artifact} className="border-b border-[var(--ss-border-subtle)]">
              <th
                scope="row"
                className="py-[var(--ss-space-2)] pr-[var(--ss-space-4)] font-normal text-[var(--ss-text-primary)]"
              >
                {row.artifact}
              </th>
              <td className="py-[var(--ss-space-2)] pr-[var(--ss-space-4)]">
                <StatusChip status={row.status} />
              </td>
              <td className="ss-mono py-[var(--ss-space-2)] pr-[var(--ss-space-4)] text-[var(--ss-text-secondary)]">
                {row.path}
              </td>
              <td className="ss-mono py-[var(--ss-space-2)] text-[var(--ss-text-muted)]">{row.cli}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
