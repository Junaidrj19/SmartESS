# SmartESS — Visual Workflow Walkthrough

This is a product walkthrough of the **current** website, written for the product owner who will demo to judges.

It is based on the rendered M10-A interface (Mission Control, Investigation History, Pipeline Readiness, and the investigation workspace for `inv-70207e0ffd15`), with `docs/m10/design.md` and `frontend/UX.md` used only to name things the product already shows.

It is **not** a coding document.

---

## 1. The one-sentence mental model

**SmartESS traces abnormal electrical behaviour from measured signals through anomaly detection, engineering calculations, evidence retrieval, competing hypotheses, validation, and a traceable report.**

That sentence is on Mission Control. It is the product.

### What is the dashboard?

The home screen is **Mission Control** at `/`.

SmartESS **does not have a traditional KPI dashboard**. There is no “health of the fleet” chart, no accuracy score as a hero number, and no “AI confidence %” tile. The first screen is an **orientation map**: what the system does, in what order, and how much stored investigation work exists on this host.

Mission Control exists so a judge who has never seen the product can answer, in the first few seconds:

- What is this?
- What is the investigation chain?
- Is the API even connected?
- How much investigation work already exists?

It is **not** where you inspect a module.

### Mission Control vs Investigation Workspace

| | Mission Control | Investigation Workspace |
| --- | --- | --- |
| Job | Orient the visitor | Inspect one completed investigation |
| Scope | The host / the product | One `investigation_id` |
| Context rail | Empty: “No module selected.” | Filled: module, test, lot, dataset, SYNTHETIC, model, status |
| Question | “What is SmartESS?” | “What happened to this module?” |

Think of Mission Control as the **front of the lab**. The Investigation Workspace is **one case file on the bench**.

---

## 2. Complete website map (as it actually exists)

There are **two navigations**. This is the main source of confusion. Both are real.

**Left sidebar (always visible)** is the *product catalogue*. Most of those items are labelled **N/I** because they would be *global* explorers (browse any module, any model, the whole knowledge base). Those backend surfaces do not exist yet, so the labels are shown but not clickable.

**Investigation tabs (only after you open a case)** are the *working product*. Those same topics — signals, M7, M8, evidence, hypotheses, report, provenance — **do** exist, but they are bound to one stored investigation.

```text
SMARTESS
│
├── Mission Control                         /          (home / orientation)
│
├── Investigation History                   /history   (index of stored cases)
│
├── Pipeline Readiness                      /system/readiness
│
├── Left-nav labels that are visible but not clickable (N/I)
│     ├── Module Explorer
│     ├── Signal Analysis          ← global live telemetry; NOT the case-file version
│     ├── Anomaly Detection        ← global M7 explorer; NOT the case-file version
│     ├── Detector Evaluation      ← global M8 explorer; NOT the case-file version
│     ├── Pipeline Trace           ← global; NOT the case-file version
│     ├── Engineering Calculations ← no dedicated page exists even inside a case
│     ├── Evidence Explorer
│     ├── Hypothesis Comparison
│     ├── Engineering Report
│     ├── Provenance
│     ├── Model / Dataset
│     └── Knowledge Base
│
└── Investigation Workspace                 /investigations/{id}
      persistent context rail (module / test / lot / dataset / SYNTHETIC / model / status)
      │
      ├── Workspace (overview)              /investigations/{id}
      ├── Pipeline Trace                    /investigations/{id}/trace
      ├── Signal Analysis                   /investigations/{id}/signals
      ├── M7 Anomaly                        /investigations/{id}/anomaly
      ├── M8 Evaluation                     /investigations/{id}/evaluation
      ├── Evidence                          /investigations/{id}/evidence
      ├── Hypotheses                        /investigations/{id}/hypotheses
      ├── Report                            /investigations/{id}/report
      └── Provenance                        /investigations/{id}/provenance
```

### What each live item is

**Mission Control** — The orientation screen. Answers: what does SmartESS do? Leads next to History, or into a recent investigation id.

**Investigation History** — A table of every stored investigation on this host (`investigation_id`, `module_id`, `model_id`, status, created time). Answers: which cases exist? Leads next to a Workspace when you click an id. **This is currently the reliable way to open a case.** History does not show evidence counts or report status; those live on the full case file.

**Pipeline Readiness** — A setup inventory of required artifacts (features, scores, evaluation, model, healthy reference, knowledge base, LLM). Every status is **UNKNOWN** because the system cannot yet ask the backend “is this artifact present?”. Answers: what must exist before investigations can run? Does not lead into a case.

**Investigation Workspace (overview)** — One-page summary of a stored case: how many calculations, evidence records, hypotheses, report sections; M7 anomaly snapshot; the two validation gates; the competing mechanisms at a glance. Answers: what did this investigation produce? Leads next into the tabs (Inspect / Trace / Compare).

**Signal Analysis** — The eight measured electrical / thermal series this investigation actually analysed, replayed from the stored record. Answers: what did the module look like over cycle number? Leads next to M7, or to the deterministic findings listed under each signal.

**M7 Anomaly** — Isolation Forest result for this module: clean / sporadic / persistent, counts, scores. Answers: did the detector flag unusual observations? Explicitly **not** “is the hardware failed?”. Leads next to M8.

**M8 Evaluation** — How that frozen detector behaved on this module, compared with an independent statistical baseline, with synthetic ground truth isolated in its own visual treatment. Answers: is the detector’s module-level call trustworthy, and does it disagree with the baseline? Leads next to Pipeline Trace (the investigation proper).

**Pipeline Trace** — The agentic run as an inspectable sequence of named stages. Answers: what did each agent do, in order, and did the gates pass? This is also where **engineering calculations** live today (there is no separate Calculations page). Leads next to Evidence, Hypotheses, Report.

**Evidence** — Passages retrieved from verified engineering documents, with citation, pages, document id, and which hypotheses cite them. Answers: what literature did the system actually retrieve? Leads next to Hypotheses (or back from a Trace link on a finding).

**Hypotheses** — Five competing candidate mechanisms from the language model, each with supporting / contradictory evidence, uncalibrated confidence, and a validation gate. Answers: what *might* explain the behaviour — and why must we not pick a winner? Leads next to Report.

**Report** — A 15-section engineering document assembled from the case, not a chat reply. Every finding is classified (observed / calculated / hypothesized / recommended). Answers: what is the written investigation outcome, with uncertainty intact? Leads next to Provenance, or Trace on an evidence id.

**Provenance** — Ordered execution log plus the lineage chain from signal → calculation → evidence → hypothesis → gate → finding. Answers: where did this conclusion come from? This is the last stop in the story.

### Intended mental model vs current navigation confusion

**Intended model:** one investigation story, stages in order.

**Current confusion:** the left sidebar looks like the product, but almost every interesting item there is greyed **N/I**. The real product is the **row of investigation tabs** that only appears after you open a case. During a demo, ignore the left-nav N/I list except History and Readiness. Work from the investigation tabs.

There is **no** dedicated “Engineering Calculations” screen. Calculations are inside Pipeline Trace (Investigation Agent) and under each signal on Signal Analysis.

You **cannot start a new investigation from the website**. The UI inspects stored cases. Launching a run is not part of this phase.

---

## 3. The website as one investigation story

Say this to a judge:

> First we look at the orientation screen so you know what SmartESS is.
> Then we open one stored investigation of a SiC power module.
> Then we inspect the measured signals.
> Then SmartESS shows what the frozen anomaly detector found (M7).
> Then it shows how that detector behaved against an independent baseline and against synthetic evaluation labels (M8) — without calling the labels a diagnosis.
> Then the agentic workflow begins: fixed engineering calculations, retrieval from a verified knowledge base, and only then a language model proposing competing mechanisms.
> Then automated gates check that every citation resolves and that the report does not assert a confirmed failure.
> Finally we read the engineering report and, if challenged, walk the provenance chain back to a page of a real document.

### Exact clicks for the canonical case `inv-70207e0ffd15`

This case is a **COMPLETED** investigation of module `syn-mod-0042` on dataset `syn-sic-pc-dev-001`, model `iforest-v1-syn-sic-pc-dev-001-s20260922`. Data origin is **SYNTHETIC**.

Mission Control’s “most recent” list only shows three ids. **`inv-70207e0ffd15` may not be one of them.** Use History.

1. Open **Mission Control** (`/`). Point at the orientation sentence and the 01–08 investigation chain. Note API **READY ok** and stored investigation coverage (currently **74** on this host: 50 COMPLETED, 24 PARTIAL).
2. Click **Investigation History**.
3. Click **`inv-70207e0ffd15`**. You land on **Investigation Workspace**.
4. Context rail now shows module `syn-mod-0042`, test `pc-sic-ref-illustrative-001`, lot `lot-01`, **SYNTHETIC**, module status **SPORADIC**, investigation **COMPLETED**.
5. Click **Signal Analysis**. Eight charts vs cycle number; 501 observations.
6. Click **M7 Anomaly**. Status **SPORADIC**, 14 of 501 observations flagged, “FAILURE CONFIRMED — NO”.
7. Click **M8 Evaluation**. Detector module verdict `y_pred_module` is **false**; statistical baseline **true**; banner **COMPARATORS DISAGREE**. Ground truth panel is hatched **SYNTHETIC — EVALUATION ONLY** and says `healthy`. Timing is **NOT APPLICABLE** (“module not in timing analysis (healthy or undetected)”).
8. Click **Pipeline Trace**. Walk Load → Investigation Agent (40 deterministic results, 5 tools) → Evidence Agent (8 queries, 5 records) → Hypothesis Agent (real LLM, 5 candidates) → Hypothesis Validation **PASSED** → Report Agent (15 sections) → Report Validation **PASSED**.
9. Click **Evidence**. Five retrieved passages with document, pages, citation, URL.
10. Click **Hypotheses**. Five cards; `gate_related` is **SUPPORTED** and **MODEL-NOMINATED PRIMARY**, not a verdict. Gate **PASSED**.
11. Click **Report**. Fifteen sections; findings classified; Human Review is **AWAITING ENGINEER REVIEW**. Optional: Export JSON / Markdown. PDF is labelled not implemented.
12. Click **Provenance**. Ordered trace including retries if any; lineage chain; evidence completeness 5/5.

That is the whole demo path that actually exists.

---

## 4. What you are looking at on each screen

### SCREEN: Mission Control

**PURPOSE:** Orient a first-time visitor. This is the home screen, not a KPI dashboard.

**WHAT I SEE:**
- Left: product nav. Most items N/I. **Mission Control**, **Investigation History**, **Pipeline Readiness** are live.
- Centre: the one-sentence product statement; API chip **READY ok** (or an error if the backend is down).
- **Investigation chain** 01–08, each tagged with a register (DATA, CALCULATED, RETRIEVED EVIDENCE, LLM, VALIDATION). On this screen the stages are **not links** (they show N/I) because they are not global explorers.
- **Module population**: honest **NOT IMPLEMENTED** (no `GET /modules`).
- **Investigation coverage**: real count from `GET /investigations` (74 on this host), status split, three most-recent ids as links, **Review** → History.

**QUESTION IT ANSWERS:** What is SmartESS, and is there real stored work here?

**WHAT I SHOULD NOTICE:**
- The chain is the product, not a marketing funnel.
- Population is unavailable on purpose; investigation coverage is real.
- API READY means the frontend is reading the live backend, not mock data.

**WHAT I CAN DO:** Open History, Readiness, or a recent investigation id.

**WHERE IT LEADS:** Investigation History, then a Workspace.

**JUDGE EXPLANATION:** “This is not a dashboard of scores. It is the map of a scientific investigation pipeline, and the only live population number here is how many stored investigations this host actually has.”

---

### SCREEN: Investigation Workspace (overview)

**PURPOSE:** One-page briefing on a stored case before you dive into stages.

**WHAT I SEE:**
- Context rail (module, test, lot, dataset, SYNTHETIC, model, sporadic/clean/persistent, investigation id, COMPLETED/PARTIAL).
- Investigation tabs: Workspace, Pipeline Trace, Signal Analysis, M7 Anomaly, M8 Evaluation, Evidence, Hypotheses, Report, Provenance.
- Four counts: **40** deterministic results (5 tools), **5** evidence records (5/5 provenance complete), **5** candidate mechanisms, **15** report sections.
- M7 snapshot: **SPORADIC**, 501 observations, 14 flagged.
- Validation: hypothesis **PASSED**, report **PASSED**.
- Five competing mechanisms in LLM-tinted rows (no winner chrome).
- Signal trajectory presence: 501 observations, 8 signals.
- Limitations: none recorded on this case.
- Reproducibility block (ids, SYNTHETIC, real LLM identity derived from the trace).

**QUESTION IT ANSWERS:** What did this investigation actually produce?

**WHAT I SHOULD NOTICE:**
- Counts are typed: CALCULATED vs RETRIEVED EVIDENCE vs LLM.
- Candidates are competing, not ranked.
- Feature/detector versions say **not recorded** — the UI refuses to invent them.

**WHAT I CAN DO:** Inspect (M7), Trace, Compare (hypotheses), Inspect (signals), or any tab.

**WHERE IT LEADS:** Usually Signal Analysis, then M7 / M8, then Trace.

**JUDGE EXPLANATION:** “This is the case file cover. Everything here is from the stored investigation record, not a live chat.”

---

### SCREEN: Signal Analysis

**PURPOSE:** Show the measured (here: synthetic) electrical and thermal series this investigation analysed.

**WHAT I SEE:**
- Summary: 501 observations, cycle range, 8 signals, anomaly-score range.
- A dashed **Scope — replay, not live telemetry** notice. This is the recorded trajectory, not a live stream.
- Eight independent charts on a shared cycle axis: RDS(on), VTH, IGSS, IDSS, VDS(on), electrical_power, Tj, Tc. Each pane is tagged **DATA**.
- Under a signal, tables of **deterministic findings** for that signal when a tool ran on it.

**QUESTION IT ANSWERS:** What was measured over life / cycle number?

**WHAT I SHOULD NOTICE:**
- Per-signal y-scales are independent; quantities are not plotted on one fake combined axis.
- There are **no per-point anomaly dots**. The record has aggregate flags, not a per-cycle `is_anomaly` series, so the UI does not invent markers.
- This is replay of what the investigation saw.

**WHAT I CAN DO:** Read charts and tool tables; switch tabs.

**WHERE IT LEADS:** M7 Anomaly.

**JUDGE EXPLANATION:** “These are the eight baseline signals the investigation actually used. We are looking at recorded measurements, not an AI drawing.”

---

### SCREEN: M7 Anomaly

**PURPOSE:** Show the frozen Isolation Forest result for this module without calling it a failure.

**WHAT I SEE:**
- Status chip **SPORADIC** next to **FAILURE CONFIRMED — NO**.
- Qualification: “Anomaly summary — not a failure diagnosis.”
- Counts: 501 observations, 14 flagged, anomaly rate ~0.028, max/mean scores, first/last anomalous cycle, lot/test/dataset ids.
- Independent **statistical baseline comparator** (robust deviation), separate from the model.
- A **NOT IMPLEMENTED** panel for per-observation score trajectory, threshold, and model hyperparameters — those need a module-level M7 endpoint that does not exist.

**QUESTION IT ANSWERS:** Did unusual observations occur, and how is that described (clean / sporadic / persistent)?

**WHAT I SHOULD NOTICE:**
- Red is not used for anomaly. Anomaly is attention, not rejection.
- Sporadic is a **rate description**, not a mechanism.
- The detector and the statistical baseline are allowed to disagree later on M8.

**WHAT I CAN DO:** Read the numbers; move to M8.

**WHERE IT LEADS:** M8 Evaluation.

**JUDGE EXPLANATION:** “M7 flagged 14 of 501 observations as statistically unusual. That is not a confirmed hardware failure. SmartESS refuses to say ‘the module is broken’ here.”

---

### SCREEN: M8 Evaluation

**PURPOSE:** Evaluate the **frozen** detector on this module. M8 does not retrain and does not change a threshold.

**WHAT I SEE:**
- Detector verdict `y_pred_module` = false; first flag cycle not applicable at module level.
- **Detection timing:** **NOT APPLICABLE** — “module not in timing analysis (healthy or undetected)”.
- **Detector vs statistical baseline:** Isolation Forest false, baseline true, **COMPARATORS DISAGREE**.
- **Ground truth** in a hatched **SYNTHETIC — EVALUATION ONLY** panel: `health_state` / `degradation_mechanism` / `degradation_stage` = healthy, `y_true` false. Caption: this is how we score the detector, not what we tell an engineer about hardware.
- **Population metrics** (precision, recall, F1): **NOT IMPLEMENTED** on this record.

**QUESTION IT ANSWERS:** How did the detector behave on this module relative to an independent check and to synthetic labels?

**WHAT I SHOULD NOTICE:**
- Ground truth is quarantined. Do not point at `healthy` as if SmartESS diagnosed health.
- Disagreement is a finding, not a bug.
- Negative lead times, when present, stay negative (flag after onset). On this canonical case, timing simply does not apply.

**WHAT I CAN DO:** Absorb the disagreement; go to Pipeline Trace.

**WHERE IT LEADS:** Pipeline Trace — this is where M9 investigation starts.

**JUDGE EXPLANATION:** “M8 is not a second detector. It asks whether the frozen M7 call is well behaved. On this module the forest and the statistical baseline disagree, and the synthetic evaluation label is kept visually separate so we never sell it as a diagnosis.”

---

### SCREEN: Pipeline Trace

**PURPOSE:** Make the agentic workflow inspectable as named stages, not as a hidden ‘AI’ button.

**WHAT I SEE:**
- An ordered list of stages with register badges (DATA / CALCULATED / RETRIEVED EVIDENCE / LLM / VALIDATION) and PASSED / REJECTED / NOT REACHED.
- Expandable detail: tools and numeric outputs; retrieval queries; LLM provider/model; report section chips.
- **Validation gates** repeated with verbatim pass/fail text.
- **Deterministic tool registry:** nine registered tools; this run invoked five (`calculate_drift`, `calculate_slope`, `calculate_percent_change`, `compare_population`, `calculate_degradation_rate`) and marks the others **NOT INVOKED**.

**QUESTION IT ANSWERS:** What ran, in what order, what kind of work each step is, and whether gates passed?

**WHAT I SHOULD NOTICE:**
- Investigation Agent: “No LLM involvement in this stage.”
- Evidence Agent: “Retrieval only — no generation.”
- Hypothesis Agent: “The only generative stage.”
- Repeated stage rows would mean real retries, not a UI glitch. This canonical run did not retry hypotheses or the report (`hypothesis_retries=0`, `report_retries=0`, `evidence_round=1`).

**WHAT I CAN DO:** Read each stage; continue to Evidence / Hypotheses / Report.

**WHERE IT LEADS:** Evidence, then Hypotheses.

**JUDGE EXPLANATION:** “This is the LangGraph path as recorded. Four named agents, two gates. Only one stage is allowed to generate language.”

---

### SCREEN: Evidence

**PURPOSE:** Show retrieved literature, not generated text, with enough provenance to open a real page.

**WHAT I SEE:**
- Counts: 5 records, 5/5 provenance complete, distinct documents, 8 queries.
- The **verbatim retrieval queries** (built from calculations by lookup tables, not by the LLM inventing search).
- Each record: quoted passage, document id, chunk id, pages, vector distance (**lower = closer**, not a star rating), citation, URL, mechanism/observable/test-condition tags, **cited by** which hypothesis.
- **Corpus context** (full library coverage): **NOT IMPLEMENTED**.

**QUESTION IT ANSWERS:** What documents did SmartESS retrieve, and can I name the page?

**WHAT I SHOULD NOTICE:**
- Visual treatment is quotation / retrieved evidence, not LLM purple.
- Missing provenance would be named, not hidden. This case is complete.
- Clicking a “cited by” id jumps to that hypothesis card.

**WHAT I CAN DO:** Follow document URLs; jump to hypotheses; jump back from report Trace links.

**WHERE IT LEADS:** Hypotheses.

**JUDGE EXPLANATION:** “These are passages pulled from the knowledge base. The model did not write them. Each one names a document, a chunk, and pages.”

---

### SCREEN: Hypotheses

**PURPOSE:** Show competing mechanisms instead of a single AI diagnosis.

**WHAT I SEE:**
- Header tagged **LLM**. Five candidates. Hypothesis id. **Model-nominated primary = `gate_related`** with note “not a verdict”. Unresolved citations = 0.
- Model note about IGSS / VTH as strongest signatures.
- **Hypothesis validation PASSED:** every cited evidence id resolves to a retrieved record.
- Five equal-weight cards (see section 9).
- Evidence ids are links back to Evidence.

**QUESTION IT ANSWERS:** What explanations are on the table, with what support and contradiction, and did citation validation pass?

**WHAT I SHOULD NOTICE:**
- No ranking bar, no winner highlight beyond a small **MODEL-NOMINATED PRIMARY** label.
- Confidence is labelled **uncalibrated model output, not a probability of physical failure**.
- Supporting and contradictory columns are equal. On this case, contradiction lists are empty — that is honest, not a hidden ‘all confirmed’.

**WHAT I CAN DO:** Open evidence ids; read distinguishing measurements; go to Report.

**WHERE IT LEADS:** Report.

**JUDGE EXPLANATION:** “The model proposed five competing mechanisms. One is marked as the model’s own nomination. SmartESS still treats them as hypotheses until an engineer says otherwise.”

---

### SCREEN: Report

**PURPOSE:** Deliver an engineering document assembled from the case, with every claim classified.

**WHAT I SEE:**
- 15 sections, finding counts by classification (this case: OBSERVED 27, CALCULATED 10, HYPOTHESIZED 10, RECOMMENDED 2, **CONFIRMED 0** — “the report gate rejects any confirmed mechanism”).
- **Report validation PASSED.**
- Section navigator.
- Each finding: label, classification, register badge, detail, source, **Trace** links to evidence ids.
- **Human Review:** dashed **AWAITING ENGINEER REVIEW**. SmartESS stores no engineer verdict.
- Export JSON, Export Markdown, **PDF — NOT IMPLEMENTED**.

**QUESTION IT ANSWERS:** What is the written outcome, how is each sentence typed, and what is still the human’s job?

**WHAT I SHOULD NOTICE:**
- Hypothesized findings keep the LLM visual treatment inside the report.
- Uncertainty and Limitations are first-class sections, not footnotes you skip.
- The report exists *because the pipeline assembled state*, not because someone asked a chatbot “write a report”.

**WHAT I CAN DO:** Jump sections; Trace to evidence; export JSON/Markdown.

**WHERE IT LEADS:** Provenance, or Evidence via Trace.

**JUDGE EXPLANATION:** “This is an engineering report. Findings are labelled observed, calculated, hypothesized, or recommended. Confirmed mechanism is zero because the gate forbids it.”

---

### SCREEN: Provenance

**PURPOSE:** Answer “where did this come from?” without opening a debugger.

**WHAT I SEE:**
- Ordered table of recorded steps (timestamp, source, description), **including repeats**.
- **Lineage chain** in plain stages: signal sample → deterministic result → evidence query → evidence record → candidate → validation gate → report finding.
- Honesty note: the hop from a specific calculation to a specific query is **not recorded** (queries are a flat list).
- Evidence completeness table (complete vs missing fields).
- Reproducibility again.
- **Frozen artifact hashes:** **NOT IMPLEMENTED** on the record.

**QUESTION IT ANSWERS:** Can I reconstruct the path from a claim back toward a document and a measurement?

**WHAT I SHOULD NOTICE:**
- Provenance is a product surface, not a log dump for developers only.
- Gaps are named (query↔finding attribution; artifact hashes).

**WHAT I CAN DO:** Read the ordered trace; return to Evidence / Report.

**WHERE IT LEADS:** End of the story, or back to any stage.

**JUDGE EXPLANATION:** “If you challenge a sentence, we do not re-prompt the model. We walk this chain.”

---

### SCREEN: Investigation History

**PURPOSE:** Index of stored cases.

**WHAT I SEE:** A table of all investigations on the host. Clickable ids. PARTIAL vs COMPLETED distinguished. Footer explaining why evidence/candidate/report columns are absent (full records are too large to fetch per row).

**QUESTION IT ANSWERS:** Which investigations exist, on which module/model, in what state?

**WHAT I SHOULD NOTICE:** 74 rows on this host. PARTIAL cases remain inspectable for completed stages.

**WHAT I CAN DO:** Open a Workspace.

**WHERE IT LEADS:** Investigation Workspace.

**JUDGE EXPLANATION:** “These are real stored runs, not demo fixtures painted in the UI.”

---

### SCREEN: Pipeline Readiness

**PURPOSE:** Show what the environment must contain before investigations make sense.

**WHAT I SEE:** An explicit **NOT IMPLEMENTED** for live artifact presence, then a table of artifacts / UNKNOWN / expected path / producing command. Then the pipeline order of scripts.

**QUESTION IT ANSWERS:** What setup does SmartESS require? (It cannot currently answer “is it present?”)

**WHAT I SHOULD NOTICE:** Missing artifact is a **setup state**, not a crash. UNKNOWN is honest.

**WHAT I CAN DO:** Read the inventory; go back to Mission Control or History.

**WHERE IT LEADS:** Not into a case.

**JUDGE EXPLANATION:** “We do not pretend the environment is green. Until a readiness endpoint exists, every artifact status is unknown.”

---

## 5. M7 → M8 → M9

```text
M7  Anomaly detection     →  “Is this module’s behaviour statistically unusual?”
M8  Detector evaluation   →  “How did that frozen detector behave? (evaluation only)”
M9  Investigation         →  “Given that, what engineering story can we investigate, retrieve, hypothesize, validate, and report?”
```

**M7 =** unsupervised Isolation Forest over the eight M6 observation features. Output is scores, flags, and a module description: **clean / sporadic / persistent**. That description is **not** a failure diagnosis.

**M8 =** an evaluation layer on **frozen** M7 artifacts. It never retrains and never moves a threshold. It reports module-level detector verdict, timing when defined, comparison to an independent statistical baseline, and synthetic ground truth used **only** to score the detector.

**M9 =** the investigation graph: load frozen artifacts → Investigation Agent (tools) → Evidence Agent (retrieval) → Hypothesis Agent (LLM) → hypothesis gate → Report Agent (deterministic assembly) → report gate.

They are separate screens because they answer different questions and must not be collapsed into “the AI found a fault.”

**How information moves:** M9 does not re-run M7 training. It **loads** the stored M7 summary, M8 evaluation fields, and the module trajectory into the investigation record. Tools then compute on those signals. Queries are built from those tool outputs. The LLM sees bounded deterministic results plus retrieved passages. The report is assembled from that state.

**Judge line:**
- “M7 detects unusual observations.”
- “M8 evaluates the detector.”
- “M9 investigates — with tools, retrieval, hypotheses, and gates — and still does not confirm a physical failure.”

On `inv-70207e0ffd15` this split is visible: M7 says **sporadic** (14 flags); M8’s detector **does not** call the module positive; the baseline **does**; synthetic ground truth is **healthy** and visually quarantined. M9 still investigates the measured drift (especially IGSS) and proposes competing mechanisms rather than overruling M8 with a fake diagnosis.

---

## 6. The agentic AI workflow

This is not a chatbot. A chatbot is: question in, paragraph out. SmartESS is a **recorded graph of named agents and gates**. You can see it on **Pipeline Trace**.

### The seven LangGraph stages (plus a recorded initialization)

As shown on Trace / Provenance for the canonical case:

```text
initialization              (run accepted)
    ↓
load_investigation          DATA          Request accepted; frozen M7/M8 artifacts identified
    ↓
investigation_agent         CALCULATED    Investigation Agent — fixed tools, no model
    ↓
evidence_agent              RETRIEVED     Evidence Agent — knowledge-base retrieval, no generation
    ↓
hypothesis_agent            LLM           Hypothesis Agent — only generative stage
    ↓
hypothesis_validation       VALIDATION    Every cited evidence id must resolve
    ↓
report_agent                CALCULATED    Report Agent — assembles state, invents nothing
    ↓
report_validation           VALIDATION    Completeness, citation resolution, no asserted certainty
```

### How each appears visually

1. **Investigation Agent** — Trace row `investigation_agent`. Tables of tool name, signal, input summary, numeric output. Copy: “No LLM involvement.” Registry shows invoked vs not invoked.
2. **Evidence Agent** — Trace row plus the **Evidence** tab. Query list, record count, provenance complete, evidence round.
3. **Hypothesis Agent** — Trace row in LLM surface (provider `openrouter`, model `nvidia/nemotron-3-ultra-550b-a55b:free` for the historical canonical run, inference **real**, 5 candidates). Full cards live on **Hypotheses**.
4. **Hypothesis Validation** — Gate card **PASSED / REJECTED / NOT REACHED** with verbatim issues. Canonical: “PASSED: every cited evidence id resolves to a retrieved record.”
5. **Report Agent** — Trace lists 15 section titles and finding counts. Full document on **Report**. Copy: “Deterministic synthesis. Recalculates nothing, invents nothing.”
6. **Report Validation** — Gate card. Canonical: “PASSED: provenance complete and no unconfirmed mechanism asserted as confirmed.”

If a gate is rejected after retries, the graph can still produce a report; the Workspace then shows a persistent **REJECTED** banner. That did **not** happen on `inv-70207e0ffd15`.

### Deterministic vs LLM

| Deterministic (code) | Retrieval (not generation) | LLM reasoning |
| --- | --- | --- |
| Load, tools, report assembly, both gates | Evidence Agent / RAG over the corpus | Hypothesis Agent only |

### Why this is agentic

- Multiple specialised stages with different jobs and different visual registers.
- Control flow includes **validation gates and retries**, not a single completion.
- State is **written down** (provenance, errors, retry counts) so a later human can inspect it.
- The language model **cannot** be the last word: a finding classified CONFIRMED is rejected by the report gate.
- The engineer still owns **Human Review**.

---

## 7. The most important visual distinction (registers)

The product’s scientific rule: **a measured number and an LLM sentence must never look like the same kind of thing.**

| Register (what you see) | What it means to a judge |
| --- | --- |
| **DATA** | What was measured or recorded from the M6/M7 artifacts (signals, observation counts, scores). |
| **CALCULATED** | What a **fixed tool** or M8 metric computed. No model in the loop. |
| **RETRIEVED EVIDENCE** | A passage **found** in a verified document. Quoted, with citation. Not authored by the LLM. |
| **LLM** | What the language model **proposes**. Requires engineering confirmation. This is the only register with a distinct hue, so the generative boundary is unmissable. |
| **VALIDATION** | Whether an automated **gate** passed or rejected, with the gate’s own words. |
| **SYNTHETIC — EVALUATION ONLY** | Injected ground truth used to **score the detector**. Never training data, never a SmartESS hardware diagnosis. Hatched so you cannot miss the quarantine. |
| **AWAITING ENGINEER REVIEW** | A human decision the system **does not store**. Dashed, empty on purpose. |

If a judge asks “is this AI?” you point at the **LLM** badge on hypotheses, then at **CALCULATED** on tools and **RETRIEVED EVIDENCE** on passages, then at **VALIDATION** on the gates.

---

## 8. Evidence → hypothesis → report

```text
Signal / investigation record
       ↓
Engineering calculation (Investigation Agent)
       ↓
Evidence retrieval / RAG (Evidence Agent)
       ↓
Evidence records (quoted passages + document + pages)
       ↓
Candidate hypotheses (Hypothesis Agent)  ← supporting / contradictory ids
       ↓
Hypothesis validation gate
       ↓
Report findings (classified) + Report validation gate
       ↓
Engineering report
       ↓
Provenance inspector
```

**Why the report is not “an LLM answer”:**
- Numeric claims in Observed Degradation come from tools, tagged **CALCULATED** or **OBSERVED**.
- Literature claims carry **Trace** links to evidence ids on the Evidence screen.
- Mechanism claims are **HYPOTHESIZED**, still in the LLM visual language.
- The Report Agent is specified as assembly of existing state.
- The report gate refuses **CONFIRMED** mechanism findings.
- Human Review is empty.

**Where citations appear:**
- Evidence records: citation text, URL, pages.
- Hypothesis cards: supporting / contradictory id lists (links).
- Report findings: **Trace** → same evidence ids.
- Provenance: ordered steps and completeness table.

**Known honesty gap:** the UI tells you it **cannot** show which specific tool result spawned which query. Do not claim that hop in a demo.

---

## 9. The Hypotheses screen

On `inv-70207e0ffd15` there are **five** candidate mechanisms. That is what this run produced (the Hypothesis Agent proposes a **set of competing explanations**, not one answer). They are:

| Mechanism | Status | Model confidence | Support / contradict | Role |
| --- | --- | --- | --- | --- |
| `gate_related` | **SUPPORTED** | 0.85 | 5 / 0 | MODEL-NOMINATED PRIMARY |
| `die_attach_thermal_path` | CANDIDATE | 0.65 | 2 / 0 | competing |
| `bond_wire_interconnect` | CANDIDATE | 0.55 | 2 / 0 | competing |
| `package_interconnect` | CANDIDATE | 0.50 | 2 / 0 | competing |
| `thermal_path` | **AMBIGUOUS** | 0.45 | 2 / 0 | competing; evidence cannot pin location |

**Supporting evidence** — retrieved records the model says favour this mechanism. Clickable.

**Contradictory evidence** — retrieved records the model says cut against it. Same visual weight. Empty means none cited, not “proven true.”

**Confidence** — the model’s own uncalibrated number. **Not** P(failure).

**MODEL-NOMINATED PRIMARY** — the backend field `primary_mechanism`. Displayed so we do not hide what the model preferred, and labelled so we do not treat it as the system’s verdict.

**Validation status** — the **gate** (all citations resolve), plus each card’s own status vocabulary: CANDIDATE, SUPPORTED, CONTRADICTED, AMBIGUOUS, INSUFFICIENT EVIDENCE.

SmartESS does **not** display “AI says the failure is X” because:

- M7 already refused to confirm failure.
- Multiple mechanisms stay on screen with equal card weight.
- Primary is a model nomination inside the LLM register.
- Distinguishing measurements tell the engineer what would actually separate the stories (e.g. TDDB / C-V for gate oxide vs SAM / Zth for die attach).
- Human Review is still awaiting.

**Judge line:** “We do not ship a single failure label. We ship five competing mechanisms, bound to retrieved evidence, with a validation gate on citations, and we still wait for an engineer.”

---

## 10. The report

**Why it exists:** An investigation that only lives in chat is not an engineering artifact. The report is the document you could hand a reliability engineer.

**What it contains (15 required sections):**
Component Information; Test Configuration; Data Quality; Observed Degradation; Anomaly Analysis; Model Results; Candidate Failure Mechanisms; Supporting Evidence; Contradictory Evidence; Uncertainty; Engineering Interpretation; Recommended Investigation; Limitations; Provenance; Human Review.

**Vs Hypotheses:** Hypotheses are the generative comparison surface. The report is the **assembled case**: measurements, calculations, anomaly, evaluation, those same candidates, uncertainty, and an empty human decision.

**Back to evidence:** Trace links on findings.

**Uncertainty:** dedicated section; hypothesized classification; CONFIRMED count forced to 0; limitations; SYNTHETIC labelled in context/reproducibility.

**Validation:** report gate must see complete provenance and must not allow an unconfirmed mechanism to be asserted as confirmed. Canonical case **PASSED**.

**Provenance:** the last tab — plus a Provenance **section inside** the report.

**Memorize:** “The report is compiled from the investigation state. It classifies every finding, forbids a confirmed mechanism, and leaves the last section for a human who has not signed anything, because the system has nowhere to store a verdict.”

---

## 11. Provenance

**Simple terms:** provenance is the **receipt**. Not the vibe of the answer — the recorded path.

**If a judge asks “Where did this conclusion come from?”**

1. Stay on the **Report**. Point at the finding’s classification (observed / calculated / hypothesized).
2. Click **Trace** on the evidence id → **Evidence** record (passage, document, pages, URL).
3. Open **Hypotheses** if the claim is a mechanism — supporting ids, status, nomination label.
4. Open **Pipeline Trace** — Hypothesis Agent (LLM identity) and the two **PASSED** gates.
5. Open **Provenance** — ordered log + lineage list.

**Chain the product actually shows:**

```text
claim (report finding)
  → finding classification + evidence_ids
  → evidence record (chunk, document, citation, pages, URL)
  → (corpus-wide library page is N/I)
  → candidate mechanism (if hypothesized)
  → validation gate
  → provenance log (which agent, when, source)
  → signal / tool output (Workspace, Signals, Trace)
```

You **cannot** today click through to a standalone corpus browser or to stored M7/M8 file hashes. Say so if asked.

---

## 12. What is implemented vs not

### A. Fully implemented and populated with real stored data

- Mission Control orientation + API health + investigation coverage counts
- Investigation History (74 real ids on this host)
- Opening a case by id
- Context rail for an open investigation (except feature/detector version, which are honestly “not recorded”)
- Workspace overview counts, M7 snapshot, gates, candidate list, trajectory presence, limitations, reproducibility
- Signal Analysis replay charts (8 signals × 501 cycles on the canonical case) + per-signal tool tables
- M7 Anomaly fields from the investigation record
- M8 Evaluation fields from the investigation record, including disagreement and quarantined ground truth
- Pipeline Trace with named agents, gates, tool registry
- Evidence Explorer with queries, records, citations, cited-by
- Hypothesis Comparison with five real candidates, gate, model-nominated primary
- Engineering Report with 15 sections, classifications, Trace, Human Review empty state, JSON/Markdown export
- Provenance table, lineage list, evidence completeness
- SYNTHETIC labelling
- Real vs mocked inference banner (canonical case is **real** inference; mocked cases show **MOCKED INFERENCE**)

### B. Implemented, but showing an unavailable / not-applicable / unknown state on purpose

- Mission Control **Module population** — screen exists; data cannot
- M7 panel “Not available from this record” (per-observation markers, threshold, model record)
- M8 **Detection timing** on this canonical module — **NOT APPLICABLE** (healthy or undetected)
- M8 **Population metrics**
- Evidence **Corpus context**
- Provenance **Frozen artifact identity** (hashes)
- Pipeline Readiness rows all **UNKNOWN**
- Report **PDF** labelled not implemented
- Reproducibility fields: feature_version, detector_version, corpus_version, artifact_hashes
- Left-nav global items shown as **N/I** rather than hidden
- Human Review always awaiting (no stored verdict)
- History omitting evidence/report columns (by design)

### C. Not implemented because the required backend endpoint does not exist

Global / projection APIs the left nav is waiting on, including roughly:

- `GET /modules`, `GET /modules/{id}`, live `GET /modules/{id}/telemetry`
- `GET /modules/{id}/anomaly` (full M7 projection)
- `GET /evaluation/{modelId}`, `GET /healthy-reference/{modelId}`
- `GET /models`
- `GET /corpus`
- Dedicated `GET /investigations/{id}/evidence`, `/provenance`, `/deterministic-results` (the UI uses the **full investigation record** instead)
- `GET /readiness`
- `POST /investigations/runs` (async launch UX)
- PDF generation

You cannot: browse the module fleet, open live telemetry for a module that has no investigation, inspect population precision/recall, browse the knowledge base as a library, see artifact hashes, start a run from the UI, or export PDF.

### D. Actual bugs / errors

No connection failure on the inspected path: API **READY**, History 200, canonical Workspace 200, all investigation tabs 200.

Do **not** call N/I or UNKNOWN a bug.

**UX confusion (not a backend error):** left nav duplicates investigation surfaces as N/I while those surfaces exist as tabs inside a case. Demo from the **investigation tabs**.

**Product gap that can trip a demo:** Mission Control only links **three** recent ids. Use **History** for `inv-70207e0ffd15`.

Hitting a PDF export URL returns an explicit unsupported-format response. That is the declared gap, not a silent crash.

---

## 13. Five-minute judge demo (`inv-70207e0ffd15`)

Tell **one** story: *unusual observations, not a confirmed failure; then an investigation that retrieves literature, proposes competing mechanisms, validates citations, and still waits for an engineer.*

**00:00–00:30 — Mission Control**  
Read the sentence. Point at the 01–08 chain. API READY. 74 stored investigations. “Not a KPI dashboard.”

**00:30–01:00 — History → open `inv-70207e0ffd15`**  
“These are stored runs. We open one case file.” Context rail: `syn-mod-0042`, **SYNTHETIC**, **SPORADIC**, **COMPLETED**.

**01:00–01:40 — Signals, then M7**  
Eight real series. M7: 14/501 flagged, **FAILURE CONFIRMED — NO**.

**01:40–02:20 — M8**  
“Now we evaluate the detector, we do not retrain it.” Comparators **disagree**. Ground truth panel is **evaluation-only / healthy**. “We do not present that label as SmartESS deciding the hardware is fine.”

**02:20–03:10 — Pipeline Trace**  
“This is where the agentic workflow begins.” Investigation Agent = 40 numbers from 5 tools, no LLM. Evidence Agent = 8 queries, 5 records. Hypothesis Agent = the only generative step, real model. Both gates **PASSED**. Point at **NOT INVOKED** tools so it is obvious the registry is real.

**03:10–03:50 — Evidence + Hypotheses**  
Quote a passage (NIST / Infineon / gate-oxide precursor). Then five cards. `gate_related` SUPPORTED + model-nominated. Others remain CANDIDATE / AMBIGUOUS. Confidence is not P(failure). Click one evidence id to show the loop.

**03:50–04:30 — Report**  
15 sections. CONFIRMED · 0. Open **Uncertainty** or **Human Review**. “The last decision is empty on purpose.”

**04:30–05:00 — Provenance**  
Ordered log. Lineage chain. “If you want to verify the conclusion, we walk this, we do not ask the model to say it again.”

If you are over time, skip Signals charts and Readiness. Do not skip M8 disagreement, Trace, Hypotheses, Human Review.

---

## 14. Judge script (say this)

“SmartESS is a scientific reliability investigation workstation for power modules. It traces measured electrical behaviour through anomaly detection, engineering calculations, retrieved literature, competing hypotheses, validation gates, and a traceable report. It is not a chatbot and it is not a KPI dashboard.

From the dashboard — Mission Control — you see that pipeline as a map, and you see how many stored investigations this host actually has. We then open one case from Investigation History: `inv-70207e0ffd15` on synthetic module `syn-mod-0042`.

We first look at the eight recorded signals. Then M7, a frozen Isolation Forest: fourteen of five hundred and one observations are flagged, status sporadic. That is an anomaly summary, not a failure diagnosis.

Then M8 evaluates that frozen detector. It does not retrain. On this module the forest and an independent statistical baseline disagree, and the synthetic evaluation labels are kept in a separate hatched register so we never present them as a hardware verdict.

This is where the agentic workflow begins — Pipeline Trace. The Investigation Agent runs fixed engineering tools: drift, slope, percent change, population comparison, degradation rate. No language model. The Evidence Agent retrieves passages from a verified knowledge base with document ids, pages, and citations. Only then does the Hypothesis Agent, a real LLM, propose mechanisms.

The Evidence Agent does not write. The Hypothesis Agent does not compute the numbers. Notice that we show five competing mechanisms, not ‘AI says the failure is X’. Gate-related is supported and is the model-nominated primary. Die attach, bond wire, package interconnect, and a more general thermal path remain on the table. Confidence is uncalibrated model output, not a probability of physical failure.

Before anything becomes a finding, hypothesis validation checks that every cited evidence id resolves to a retrieved record. Report validation checks completeness and forbids asserting a confirmed mechanism. Both passed on this run.

Finally the report is fifteen engineering sections assembled from that state. Findings are classified observed, calculated, hypothesized, or recommended. Confirmed is zero. Human review is awaiting an engineer, because SmartESS stores no verdict.

If you want to verify the conclusion, we do not re-prompt the model. We open Provenance and Trace a claim to an evidence record and a page of a real document.”

---

## 15. Thirty-second version

“SmartESS is an investigation workstation, not an AI dashboard. You open a stored case, inspect the measured signals, see what a frozen anomaly detector flagged — without calling it a failure — then evaluate that detector. After that, named agents calculate, retrieve literature, and only then propose competing hypotheses. Gates check citations and forbid fake certainty. The report is a classified engineering document, and provenance is how we show a judge where a sentence came from.”

---

## Demo cheat sheet for `inv-70207e0ffd15`

| Fact | Value |
| --- | --- |
| Status | COMPLETED |
| Module | syn-mod-0042 |
| Data | SYNTHETIC |
| M7 | SPORADIC · 14 / 501 · failure confirmed: NO |
| M8 detector vs baseline | disagree (false vs true) |
| M8 ground truth | healthy — evaluation only |
| Tools | 40 results, 5 of 9 invoked |
| Evidence | 5/5 provenance complete, 8 queries |
| Hypotheses | 5 competing; `gate_related` SUPPORTED, model-nominated |
| LLM | real (OpenRouter / Nemotron — historical canonical run) |
| Gates | both PASSED |
| Report | 15 sections · CONFIRMED 0 · human review empty |
)
