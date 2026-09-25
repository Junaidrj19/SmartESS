import { MonoId } from "@/components/MonoId";
import type { InvestigationRecord } from "@/lib/types/backend";
import { llmIdentity, asString } from "@/lib/investigation";

/**
 * ReproducibilityBlock — what exact configuration produced this investigation
 * (UX.md §21; design.md §13.3).
 *
 * Fields the record does not carry are shown as `not recorded` rather than
 * inferred (design.md §13.4):
 *  · feature_version / detector_version — on model-record.json, not exposed;
 *  · corpus_version and chunk count at investigation time — not recorded;
 *  · artifact hashes — produced by `snapshot_m7_m8()` but not persisted;
 *  · LLM provider/model — parsed from the provenance source string, so labelled
 *    DERIVED FROM PROVENANCE.
 */
export function ReproducibilityBlock({ record }: { record: InvestigationRecord }) {
  const llm = llmIdentity(record);
  const m7 = record.m7_module_summary;

  return (
    <dl className="grid grid-cols-1 gap-[var(--ss-space-3)] p-[var(--ss-space-4)] sm:grid-cols-2 lg:grid-cols-3">
      <Row label="investigation_id" value={record.investigation_id} />
      <Row label="created_at" value={record.created_at} />
      <Row label="status" value={record.status} />

      <Row label="module_id" value={record.module_id} />
      <Row label="test_id" value={asString(m7["test_id"])} />
      <Row label="lot_id" value={asString(m7["lot_id"])} />

      <Row label="dataset_id" value={record.dataset_id} />
      <Row label="data_origin" value="SYNTHETIC" note="Development dataset. Not production telemetry." />
      <Row label="model_id" value={record.model_id} />

      <Row label="feature_version" value={null} note="On model-record.json; not exposed by any endpoint." />
      <Row label="detector_version" value={null} note="On model-record.json; not exposed by any endpoint." />
      <Row label="module_anomaly_status" value={asString(m7["module_anomaly_status"])} />

      <Row
        label="llm_provider"
        value={llm.provider}
        note="Derived from the hypothesis_agent provenance source string."
      />
      <Row
        label="llm_model"
        value={llm.model}
        note="Derived from the hypothesis_agent provenance source string."
      />
      <Row
        label="inference"
        value={llm.mode === "UNKNOWN" ? null : llm.mode}
        note="Derived from the provenance source string plus any recorded provider error."
      />

      <Row
        label="retry_counts"
        value={
          Object.keys(record.retry_counts).length === 0
            ? null
            : Object.entries(record.retry_counts)
                .map(([k, v]) => `${k}=${v}`)
                .join(" · ")
        }
      />
      <Row label="corpus_version" value={null} note="Not recorded at investigation time." />
      <Row label="artifact_hashes" value={null} note="snapshot_m7_m8() is computed but not persisted." />
    </dl>
  );
}

function Row({
  label,
  value,
  note,
}: {
  label: string;
  value: string | null;
  note?: string;
}) {
  return (
    <div className="flex flex-col gap-[var(--ss-space-1)]">
      <dt className="ss-field-label">{label}</dt>
      <dd className="m-0 flex flex-col gap-[var(--ss-space-1)]">
        <MonoId value={value} />
        {note && (
          <span className="text-[var(--ss-text-muted)]" style={{ fontSize: "var(--ss-text-label-size)" }}>
            {note}
          </span>
        )}
      </dd>
    </div>
  );
}
