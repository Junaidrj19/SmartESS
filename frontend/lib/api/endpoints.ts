/**
 * The SmartESS API surface consumed by the frontend.
 *
 * Verified against `backend/api/app.py`, `backend/api/investigations.py`,
 * `backend/api/modules.py` and `backend/api/system.py`.
 *
 * Nothing here fabricates a response. An endpoint that does not exist is
 * declared with `notImplemented` so the UI renders an explicit readiness state
 * (UX.md §43.2; design.md §14).
 */

import { api, notImplemented, type ApiResult } from "@/lib/api/client";
import type {
  HealthResponse,
  InvestigationCreated,
  InvestigationListItem,
  InvestigationRecord,
  InvestigationReport,
  InvestigationRequest,
  Hypothesis,
} from "@/lib/types/backend";
import type {
  Corpus,
  CorpusDocument,
  EvaluationSummary,
  HealthyReference,
  ModelListItem,
  ModuleAnomaly,
  ModuleDetail,
  ModulePage,
  ModulePopulation,
  ProvenanceBundle,
  Readiness,
  TelemetrySeries,
} from "@/lib/types/m10";

/** Artifacts are immutable once written; the investigation list grows. */
const CACHE_ARTIFACT = 300;
const CACHE_LIST = 30;

/* ── system ────────────────────────────────────────────────────────────── */

export function getHealth(): Promise<ApiResult<HealthResponse>> {
  return api.request<HealthResponse>("/health");
}

export function getReadiness(modelId?: string): Promise<ApiResult<Readiness>> {
  const q = modelId ? `?model_id=${encodeURIComponent(modelId)}` : "";
  return api.request<Readiness>(`/readiness${q}`);
}

export function getCorpus(): Promise<ApiResult<Corpus>> {
  return api.request<Corpus>("/corpus", { revalidateSeconds: CACHE_ARTIFACT });
}

export function getCorpusDocument(documentId: string): Promise<ApiResult<CorpusDocument>> {
  return api.request<CorpusDocument>(
    `/corpus/documents/${encodeURIComponent(documentId)}`,
    { revalidateSeconds: CACHE_ARTIFACT },
  );
}

/* ── models ────────────────────────────────────────────────────────────── */

export function listModels(): Promise<ApiResult<ModelListItem[]>> {
  return api.request<ModelListItem[]>("/models", { revalidateSeconds: CACHE_ARTIFACT });
}

export function getModel(modelId: string): Promise<ApiResult<Record<string, unknown>>> {
  return api.request<Record<string, unknown>>(
    `/models/${encodeURIComponent(modelId)}`,
    { revalidateSeconds: CACHE_ARTIFACT },
  );
}

/* ── modules ───────────────────────────────────────────────────────────── */

export interface ModuleQuery {
  model_id?: string;
  lot_id?: string;
  anomaly_status?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export function listModules(query: ModuleQuery = {}): Promise<ApiResult<ModulePage>> {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
  }
  const q = params.size > 0 ? `?${params.toString()}` : "";
  return api.request<ModulePage>(`/modules${q}`, { revalidateSeconds: CACHE_ARTIFACT });
}

export function getModulePopulation(modelId?: string): Promise<ApiResult<ModulePopulation>> {
  const q = modelId ? `?model_id=${encodeURIComponent(modelId)}` : "";
  return api.request<ModulePopulation>(`/modules/population${q}`, {
    revalidateSeconds: CACHE_ARTIFACT,
  });
}

export function getModule(
  moduleId: string,
  modelId?: string,
): Promise<ApiResult<ModuleDetail>> {
  const q = modelId ? `?model_id=${encodeURIComponent(modelId)}` : "";
  // Not cached: it embeds the live investigation list for this module.
  return api.request<ModuleDetail>(`/modules/${encodeURIComponent(moduleId)}${q}`);
}

export interface TelemetryQuery {
  model_id?: string;
  signals?: string[];
  from_cycle?: number;
  to_cycle?: number;
  max_points?: number;
}

export function getTelemetry(
  moduleId: string,
  query: TelemetryQuery = {},
): Promise<ApiResult<TelemetrySeries>> {
  const params = new URLSearchParams();
  if (query.model_id) params.set("model_id", query.model_id);
  if (query.signals?.length) params.set("signals", query.signals.join(","));
  if (query.from_cycle !== undefined) params.set("from_cycle", String(query.from_cycle));
  if (query.to_cycle !== undefined) params.set("to_cycle", String(query.to_cycle));
  if (query.max_points !== undefined) params.set("max_points", String(query.max_points));
  const q = params.size > 0 ? `?${params.toString()}` : "";
  return api.request<TelemetrySeries>(
    `/modules/${encodeURIComponent(moduleId)}/telemetry${q}`,
    { revalidateSeconds: CACHE_ARTIFACT },
  );
}

export function getModuleAnomaly(
  moduleId: string,
  modelId?: string,
): Promise<ApiResult<ModuleAnomaly>> {
  const q = modelId ? `?model_id=${encodeURIComponent(modelId)}` : "";
  return api.request<ModuleAnomaly>(
    `/modules/${encodeURIComponent(moduleId)}/anomaly${q}`,
    { revalidateSeconds: CACHE_ARTIFACT },
  );
}

/* ── evaluation ────────────────────────────────────────────────────────── */

export function getEvaluation(modelId: string): Promise<ApiResult<EvaluationSummary>> {
  return api.request<EvaluationSummary>(
    `/evaluation/${encodeURIComponent(modelId)}`,
    { revalidateSeconds: CACHE_ARTIFACT },
  );
}

export function getHealthyReference(modelId: string): Promise<ApiResult<HealthyReference>> {
  return api.request<HealthyReference>(
    `/healthy-reference/${encodeURIComponent(modelId)}`,
    { revalidateSeconds: CACHE_ARTIFACT },
  );
}

/* ── investigations ────────────────────────────────────────────────────── */

export function listInvestigations(filter?: {
  module_id?: string;
  model_id?: string;
}): Promise<ApiResult<InvestigationListItem[]>> {
  const params = new URLSearchParams();
  if (filter?.module_id) params.set("module_id", filter.module_id);
  if (filter?.model_id) params.set("model_id", filter.model_id);
  const q = params.size > 0 ? `?${params.toString()}` : "";
  return api.request<InvestigationListItem[]>(`/investigations${q}`, {
    revalidateSeconds: CACHE_LIST,
  });
}

export function getInvestigation(
  investigationId: string,
): Promise<ApiResult<InvestigationRecord>> {
  return api.request<InvestigationRecord>(
    `/investigations/${encodeURIComponent(investigationId)}`,
    { revalidateSeconds: CACHE_ARTIFACT },
  );
}

export function getInvestigationReport(
  investigationId: string,
): Promise<ApiResult<InvestigationReport | null>> {
  return api.request<InvestigationReport | null>(
    `/investigations/${encodeURIComponent(investigationId)}/report`,
    { revalidateSeconds: CACHE_ARTIFACT },
  );
}

export function getInvestigationProvenance(
  investigationId: string,
): Promise<ApiResult<ProvenanceBundle>> {
  return api.request<ProvenanceBundle>(
    `/investigations/${encodeURIComponent(investigationId)}/provenance`,
    { revalidateSeconds: CACHE_ARTIFACT },
  );
}

export function getInvestigationHypothesis(
  investigationId: string,
): Promise<ApiResult<Hypothesis | null>> {
  return api.request<Hypothesis | null>(
    `/investigations/${encodeURIComponent(investigationId)}/hypothesis`,
    { revalidateSeconds: CACHE_ARTIFACT },
  );
}

/**
 * `POST /investigations` — **synchronous**. The request blocks for the whole
 * graph run, including every LLM call, so a real run can take minutes
 * (design.md §19.10). No progress is simulated while it is in flight.
 */
export function createInvestigation(
  body: InvestigationRequest,
): Promise<ApiResult<InvestigationCreated>> {
  return api.request<InvestigationCreated>("/investigations", {
    method: "POST",
    body,
    timeoutMs: 15 * 60 * 1000,
  });
}

/* ── still not implemented in the backend ──────────────────────────────── */

/**
 * Capabilities the backend genuinely does not provide. Kept explicit so a
 * surface that needs one renders a named readiness state rather than an empty
 * panel.
 */
export const unavailable = {
  /** Asynchronous run + per-stage live progress (design.md §10.3). */
  runs: <T,>() =>
    notImplemented<T>("POST /investigations/runs", "design.md §10.3 — synchronous POST is used instead"),
  /** Global evidence lookup: ChromaRetriever has no get-by-chunk-id. */
  evidenceById: <T,>(evidenceId: string) =>
    notImplemented<T>(`GET /evidence/${evidenceId}`, "design.md §20.12 — evidence is investigation-scoped"),
  /** A real ModuleProfile / TestProfile is not wired into an investigation. */
  moduleProfile: <T,>(moduleId: string) =>
    notImplemented<T>(`GET /modules/${moduleId}/profile`, "design.md §20.1 — profile binding not implemented"),
  /** Engineer verdict / sign-off has no storage anywhere. */
  humanReview: <T,>(investigationId: string) =>
    notImplemented<T>(
      `POST /investigations/${investigationId}/review`,
      "design.md §20.6 — no field exists for an engineer decision",
    ),
} as const;
