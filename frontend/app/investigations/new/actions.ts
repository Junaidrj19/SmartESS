"use server";

import { redirect } from "next/navigation";
import { createInvestigation } from "@/lib/api/endpoints";

/**
 * Server action for launching an investigation.
 *
 * `POST /investigations` is synchronous: it runs the whole LangGraph pipeline,
 * including LLM calls, before returning. This action therefore waits for the
 * real response and **simulates nothing** (UX.md §29; design.md §21).
 *
 * The investigation id comes from the backend. The frontend never generates one.
 */
export interface LaunchState {
  status: "idle" | "error";
  message?: string;
  detail?: string;
}

export async function launchInvestigation(
  _prev: LaunchState,
  formData: FormData,
): Promise<LaunchState> {
  const moduleId = String(formData.get("module_id") ?? "").trim();
  const modelId = String(formData.get("model_id") ?? "").trim();
  const datasetId = String(formData.get("dataset_id") ?? "").trim();
  const maxEvidenceRaw = String(formData.get("max_evidence") ?? "5").trim();

  if (!moduleId) {
    return { status: "error", message: "A module id is required." };
  }

  const maxEvidence = Number.parseInt(maxEvidenceRaw, 10);
  if (!Number.isFinite(maxEvidence) || maxEvidence < 1) {
    return { status: "error", message: "Evidence limit must be a positive integer." };
  }

  const result = await createInvestigation({
    module_id: moduleId,
    model_id: modelId || undefined,
    dataset_id: datasetId || undefined,
    max_evidence: maxEvidence,
  });

  if (result.kind !== "ok") {
    const detail =
      result.kind === "not-implemented"
        ? `${result.endpoint} — ${result.reference}`
        : result.kind === "not-found"
          ? `404 — ${result.detail}`
          : result.kind === "unreachable"
            ? `API unreachable — ${result.detail}`
            : `${result.status} — ${result.detail}`;
    return {
      status: "error",
      message:
        result.kind === "not-found"
          ? "The backend could not find that module or a required frozen artifact."
          : "The investigation did not start.",
      detail,
    };
  }

  // Navigate to the id the backend returned.
  redirect(`/investigations/${result.data.investigation_id}`);
}
