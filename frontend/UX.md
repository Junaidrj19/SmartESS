# SmartESS M10 — Frontend UX Specification

> Status: UX DESIGN / IMPLEMENTATION CONTRACT  
> Source of truth: `design.md` for backend semantics, data contracts, epistemic rules, and M10 boundaries.  
> This document reorganises those constraints into a user-facing experience specification.
>
> **Core objective:** An engineer or judge who has never seen SmartESS before must understand what the system does, what the ML layer found, what the investigation agents did, what evidence was retrieved, what hypotheses were generated, how those hypotheses were validated, and how the final report is traceable — without reading the repository or documentation.

---

## 1. The frontend is not a dashboard

SmartESS must not look like a generic AI SaaS dashboard.

It is an engineer-facing scientific investigation workstation.

The interface should communicate:

```text
MEASURED DATA
    ↓
FEATURE / SIGNAL ANALYSIS
    ↓
M7 ANOMALY DETECTION
    ↓
M8 DETECTOR EVALUATION
    ↓
M9 INVESTIGATION
    ├── Deterministic engineering calculations
    ├── Evidence retrieval from verified technical literature
    ├── LLM hypothesis reasoning
    └── Validation gates
    ↓
COMPETING MECHANISMS
    ↓
ENGINEERING REPORT
    ↓
FULL PROVENANCE
```

This workflow is the product.

Do not hide it behind a generic "AI Analysis" button.

Do not replace it with a chat interface.

Do not reduce it to KPI cards.

The frontend exists to make the existing M1–M9 engineering work visible, navigable, and traceable.

---

## 2. The three comprehension tests

The UI must pass three levels of understanding.

### After 30 seconds

A first-time user should be able to answer:

- What is SmartESS?
- What module/test am I looking at?
- Is the data synthetic or production?
- Is the module anomalous?
- What happened after anomaly detection?
- Where does the AI/agentic investigation begin?

The first screen must therefore establish context before interpretation.

### After 2 minutes

The user should understand the investigation pipeline:

```text
Module
  → Signals
  → M7 anomaly detector
  → M8 detector evaluation
  → Investigation Agent
  → Evidence Agent
  → Hypothesis Agent
  → Validation
  → Report Agent
  → Report Validation
```

The user should be able to click into every stage.

### After 5 minutes

The user should be able to demonstrate:

1. A real signal observation.
2. The corresponding anomaly score.
3. The detector's behaviour and evaluation.
4. A deterministic engineering calculation.
5. The evidence query generated from the investigation.
6. The retrieved technical source.
7. A competing mechanism.
8. Supporting and contradictory evidence.
9. The hypothesis-validation result.
10. The final report finding.
11. The complete provenance chain back to the source.

If the interface cannot support this walkthrough, it is not exposing the depth of SmartESS.

---

## 3. Primary navigation

Use a persistent application shell.

Recommended navigation:

```text
SMARTESS
Scientific Reliability Investigation

[Mission Control]

INVESTIGATION
  Module Explorer
  Signal Analysis
  Anomaly Detection
  Detector Evaluation

M9 INVESTIGATION
  Pipeline Trace
  Engineering Calculations
  Evidence Explorer
  Hypothesis Comparison
  Engineering Report
  Provenance

SYSTEM
  Investigation History
  Model / Dataset
  Knowledge Base
  Pipeline Readiness
```

The exact visual arrangement may be left or top navigation, but the investigation context must remain persistent.

The navigation must never make the user guess where the agentic workflow is.

The four agent stages must be visible as first-class concepts:

```text
Investigation Agent
Evidence Agent
Hypothesis Agent
Report Agent
```

Validation stages are separate from agents:

```text
Hypothesis Validation
Report Validation
```

Do not label the whole system simply "AI".

---

## 4. Persistent context rail

The context rail is always visible while an investigation is open.

Minimum fields:

```text
MODULE
syn-mod-0042

TEST
<test_id>

LOT
<lot_id>

DATASET
syn-sic-pc-dev-001

DATA ORIGIN
SYNTHETIC

MODEL
iforest-v1-syn-sic-pc-dev-001-s20260922

FEATURE VERSION
v1

DETECTOR VERSION
v1

MODULE STATUS
sporadic / clean / persistent

INVESTIGATION
inv-70207e0ffd15

STATUS
COMPLETED / PARTIAL / ...
```

Machine identifiers use monospace.

The context rail must survive route changes and panel-level API errors.

Never make the user wonder which module they are currently inspecting.

---

## 5. First screen — Mission Control

The first screen is NOT a marketing landing page.

It is Mission Control / Module Explorer.

Its job is orientation.

### Top orientation band

Immediately explain the system in one compact sentence:

> SmartESS traces abnormal electrical behaviour from measured signals through anomaly detection, engineering calculations, evidence retrieval, competing hypotheses, validation, and a traceable report.

Below that, show the investigation chain as a compact process map:

```text
DATA
  ↓
M7 DETECTOR
  ↓
M8 EVALUATION
  ↓
DETERMINISTIC ANALYSIS
  ↓
EVIDENCE RETRIEVAL
  ↓
LLM HYPOTHESES
  ↓
VALIDATION
  ↓
ENGINEERING REPORT
```

This is an orientation device, not decorative animation.

Each stage is clickable.

### Population area

Show:

- 750-module population context when available.
- lot distribution.
- `clean`, `sporadic`, `persistent` counts.
- model identity.
- dataset identity.
- data origin.
- investigation coverage.

`module_anomaly_status` must always carry the qualification:

> Anomaly summary — not a failure diagnosis.

Do not use giant KPI tiles.

Use a dense analytical table or compact population view.

### Module table

The module explorer must support:

- module selection;
- lot filtering;
- anomaly-status filtering;
- split membership;
- sorting;
- search.

The user should be able to select a module and immediately enter its engineering context.

---

## 6. Module Context — the bridge between ML and investigation

Once a module is selected, the first module-level screen should answer:

> What was observed, what did the detector do, and what can I investigate?

Recommended structure:

```text
┌─────────────────────────────────────────────────────────────┐
│ MODULE CONTEXT                                              │
│ syn-mod-0042 · lot-XX · synthetic                          │
├─────────────────────────────────────────────────────────────┤
│ SIGNALS                 │ DETECTOR                          │
│ 8 measured trajectories │ anomaly score                     │
│                         │ module status                     │
│                         │ first flag                         │
├─────────────────────────┴───────────────────────────────────┤
│ M8 DETECTOR BEHAVIOUR                                       │
│ evaluation · timing · baseline comparison                   │
├─────────────────────────────────────────────────────────────┤
│ INVESTIGATION                                               │
│ Existing investigation: inv-...                             │
│ [Open Investigation] [Run Investigation]                    │
└─────────────────────────────────────────────────────────────┘
```

The user must see the M7/M8 context adjacent to the investigation launch.

This prevents the LLM hypothesis from being interpreted without the underlying detector context.

---

## 7. Signal Analysis

The signal view is the scientific foundation of the workspace.

Display the eight baseline/rolling signals:

```text
RDS_on
VTH
IGSS
IDSS
VDS_on
electrical_power
Tj
Tc
```

Do not offer `VF` as a health signal.

### Chart architecture

Use synchronized stacked panes:

```text
RDS_on          ───────────────────────
VTH             ───────────────────────
IGSS            ───────────────────────
IDSS            ───────────────────────
VDS_on          ───────────────────────
electrical_power──────────────────────
Tj              ───────────────────────
Tc              ───────────────────────
ANOMALY SCORE   ───────────────────────
FLAGS           |   |       |    |
                ↑
             shared cycle
             crosshair
```

All panes share `cycle_number`.

A single hover position reports the same cycle across all panes.

Each signal gets its own y-scale.

Never imply that signals with different physical scales share a numerical magnitude.

### Required chart interactions

- signal visibility;
- cycle-range zoom;
- reset;
- synchronized crosshair;
- exact-value tooltip;
- observation index;
- tabular data view.

Null values must produce line breaks.

Never interpolate missing data.

If server-side downsampling occurred, show:

> Downsampled view — flagged observations retained.

Do not silently downsample.

---

## 8. M7 Anomaly Detection

The M7 view answers:

> Did the frozen detector identify statistically unusual observations, and where?

Show:

- anomaly-score trajectory;
- anomaly threshold;
- `is_anomaly` markers;
- module anomaly summary;
- model identity;
- statistical-baseline comparator;
- detector configuration.

State explicitly:

> Higher anomaly score = more anomalous.

Do not imply that negative anomaly scores mean "good".

Do not call anomaly detection a failure diagnosis.

Use:

> ANOMALY DETECTED

only for detector output.

Never:

> FAILURE CONFIRMED

unless a future human decision layer explicitly records such a decision. The current backend does not.

The M7 panel should always contain:

> Anomaly detection is a statistical finding, not a physical failure diagnosis.

---

## 9. M8 Detector Evaluation

M8 is where SmartESS proves that the detector itself is being evaluated.

Show the two populations separately:

```text
OVERALL POPULATION
750 modules

M7 TEST-LOT COMPATIBILITY
300 modules
```

Show each population's:

- TP
- TN
- FP
- FN
- precision
- recall
- F1
- FPR

Never blend the populations.

### Timing panel

Use:

```text
lead_vs_onset (cycles)
negative = flagged after onset
```

The axis must cross zero.

Do not rename this into a positive-sounding "early warning" metric.

Negative timing is an actual engineering result and must remain visible.

If the module is absent from timing analysis, show the backend note:

> module not in timing analysis (healthy or undetected)

Do not display a fake zero.

### Ground truth

Ground truth must live in a visibly separate register:

```text
GROUND TRUTH
SYNTHETIC — EVALUATION ONLY
```

It must never visually resemble SmartESS output.

---

## 10. The agentic workflow — primary UX requirement

The agentic workflow must be visible without opening documentation.

This is one of the most important requirements of M10.

The user should be able to see:

```text
                    INVESTIGATION
                         │
                         ▼
               ┌──────────────────┐
               │ Investigation    │
               │ Agent            │
               │ DETERMINISTIC    │
               └────────┬─────────┘
                        │
                        ▼
               ┌──────────────────┐
               │ Evidence Agent   │
               │ RAG RETRIEVAL    │
               └────────┬─────────┘
                        │
                        ▼
               ┌──────────────────┐
               │ Hypothesis Agent  │
               │ LLM REASONING    │
               └────────┬─────────┘
                        │
                        ▼
               ┌──────────────────┐
               │ Hypothesis       │
               │ Validation       │
               │ GATE             │
               └────────┬─────────┘
                        │
                        ▼
               ┌──────────────────┐
               │ Report Agent     │
               │ SYNTHESIS        │
               └────────┬─────────┘
                        │
                        ▼
               ┌──────────────────┐
               │ Report Validation│
               │ GATE             │
               └──────────────────┘
```

Also expose the underlying seven LangGraph nodes:

```text
load_investigation
investigation_agent
evidence_agent
hypothesis_agent
hypothesis_validation
report_agent
report_validation
```

`START` and `END` may be shown as graph boundaries but are not counted as investigation stages.

### Critical distinction

The interface must teach the user that these stages are different kinds of computation.

```text
DETERMINISTIC
Investigation Agent

RETRIEVAL
Evidence Agent

GENERATIVE
Hypothesis Agent

VALIDATION
Hypothesis Validation

SYNTHESIS
Report Agent

VALIDATION
Report Validation
```

This is more informative than a generic "AI processing" indicator.

---

## 11. Pipeline Trace

Pipeline Trace is the central M9 interface.

Do not render it as decorative animation.

It is an inspectable execution trace.

Each stage is expandable.

Example:

```text
01  load_investigation       COMPLETED
02  investigation_agent      COMPLETED
03  evidence_agent           COMPLETED
04  hypothesis_agent         COMPLETED
05  hypothesis_validation    PASSED
06  report_agent             COMPLETED
07  report_validation        PASSED
```

If retries occurred, preserve them in chronological order.

Never deduplicate provenance entries.

### Stage header

Every stage should show:

```text
STAGE
SOURCE
STATUS
INPUT COUNT
OUTPUT COUNT
RETRIES
REGISTER
```

Then the user can expand the stage.

---

## 12. Investigation Agent inspector

This stage must clearly state:

> DETERMINISTIC — NO LLM INVOLVEMENT

Show:

- loaded artifacts;
- tools invoked;
- result counts;
- signal associated with each result;
- tool version;
- input summary;
- output;
- provenance method;
- healthy-reference status.

For the canonical investigation:

```text
40 results
5 invoked tools
```

Show the four registered but unused tools as:

```text
NOT INVOKED
```

Do not imply that registered tools were executed.

---

## 13. Evidence Agent inspector

This stage must clearly state:

> RETRIEVAL — NO LLM GENERATION

Show:

- evidence queries;
- query round;
- number of retrieved records;
- `max_evidence`;
- signal/tool attribution;
- provenance completeness;
- retrieval status.

If signal/tool attribution was reconstructed by M10, label it:

> DERIVED

Never call derived relationships recorded provenance.

### Retrieval semantics

Display vector distance exactly as:

> vector distance (lower = closer)

Never render distance as:

- relevance %;
- confidence %;
- score bar;
- star rating.

---

## 14. Hypothesis Agent inspector

This is the visually distinct generative stage.

Header:

```text
LLM REASONING
```

Show:

```text
PROVIDER
MODEL
ENDPOINT
INFERENCE
PROMPT VERSION
TEMPERATURE
MAX TOKENS
```

The inference state must be unmistakable:

```text
REAL INFERENCE
```

or:

```text
MOCKED INFERENCE
NO MODEL-GENERATED REASONING
```

A mocked run receives a persistent warning banner.

Show:

- candidate ids;
- mechanisms;
- status;
- model-assigned confidence;
- reasoning;
- supporting evidence ids;
- contradictory evidence ids;
- distinguishing measurements;
- context limits applied.

The UI must explicitly say:

> Confidence is model-assigned confidence in this candidate, not probability of physical failure.

Never aggregate confidence into a failure probability.

Never rank candidates into a winner.

---

## 15. Validation gates

Validation must look different from generation.

Use explicit gate treatment:

```text
HYPOTHESIS VALIDATION
PASSED

4 checks
0 issues
```

or:

```text
HYPOTHESIS VALIDATION
REJECTED

3 issues
2 retries exhausted
```

Show the actual issues.

Show rejected evidence ids individually.

Show the routing decision.

The same treatment applies to `report_validation`.

A report may exist after a rejected hypothesis gate. If so, the report must retain the rejection marker.

Never hide failed validation merely because a later stage completed.

---

## 16. Evidence Explorer

Evidence Explorer is a first-class RAG interface, not a bibliography drawer.

Each evidence record shows:

```text
EVIDENCE ID
DOCUMENT ID
CHUNK ID

CITATION
PAGE RANGE

SOURCE TYPE
VERIFICATION STATUS

MECHANISMS
OBSERVABLES
TEST CONDITIONS

VECTOR DISTANCE
lower = closer

RETRIEVED PASSAGE
```

The user must be able to move:

```text
Evidence
   ↓
Source document
   ↓
Corpus metadata
   ↓
Official source
```

Only verified corpus documents belong in the production evidence collection.

If provenance cannot resolve to a document, show:

> UNRESOLVED PROVENANCE

Do not silently convert it into a normal citation.

---

## 17. Hypothesis Comparison

This is not a winner-selection screen.

It is a scientific comparison of competing explanations.

Use equal-weight columns/cards for candidates.

Example:

```text
┌────────────────────┬────────────────────┬────────────────────┐
│ Candidate A        │ Candidate B        │ Candidate C        │
│ bond-wire...       │ gate-related      │ die-attach...      │
│ CANDIDATE           │ SUPPORTED         │ AMBIGUOUS          │
├────────────────────┼────────────────────┼────────────────────┤
│ Supporting         │ Supporting         │ Supporting         │
│ evidence           │ evidence           │ evidence           │
├────────────────────┼────────────────────┼────────────────────┤
│ Contradictory      │ Contradictory      │ Contradictory      │
│ evidence           │ evidence           │ evidence           │
├────────────────────┼────────────────────┼────────────────────┤
│ Reasoning          │ Reasoning          │ Reasoning          │
├────────────────────┼────────────────────┼────────────────────┤
│ Distinguishing     │ Distinguishing     │ Distinguishing     │
│ measurements       │ measurements       │ measurements       │
└────────────────────┴────────────────────┴────────────────────┘
```

No candidate gets a winner badge.

If `primary_mechanism` exists, label it:

> MODEL-NOMINATED PRIMARY

and keep it in the LLM register.

Do not reinterpret it as the physical diagnosis.

---

## 18. Engineering Report

The report is an engineering document, not a chatbot response.

All 15 report sections must be navigable.

Use a section navigator:

```text
01 ...
02 ...
03 ...
...
15 ...
```

Every finding must visibly carry its classification:

```text
OBSERVED
CALCULATED
PREDICTED
HYPOTHESIZED
CONFIRMED
RECOMMENDED
```

The interface must preserve uncertainty.

Examples:

```text
INSUFFICIENT EVIDENCE
AMBIGUOUS
ANOMALY DETECTED — MECHANISM UNRESOLVED
MODEL NOT SUITABLE FOR DECISION SUPPORT
```

Do not upgrade uncertainty through visual emphasis.

### Finding trace

Every finding should expose:

```text
Finding
  ↓
Evidence IDs
  ↓
Evidence record
  ↓
Chunk
  ↓
Corpus document
```

The user must never lose module/investigation context while tracing.

---

## 19. Human Review

The current backend does not store an engineer decision.

Therefore the interface must show:

```text
HUMAN DECISION

Awaiting engineer review
```

Do not pre-fill it.

Do not simulate confirmation.

`CONFIRMED` treatment may exist in the component system because the vocabulary requires it, but the current report validation rejects confirmed mechanism findings.

---

## 20. Provenance Inspector

Provenance is a primary product surface, not a developer debug panel.

Every important claim should have a `Trace` affordance.

The inspector should show the ordered provenance path:

```text
initialization
    ↓
load_investigation
    ↓
investigation_agent
    ↓
evidence_agent
    ↓
hypothesis_agent
    ↓
hypothesis_validation
    ↓
report_agent
    ↓
report_validation
```

Repeated stages remain repeated.

Also show:

```text
MODEL ID
DATASET ID
FEATURE VERSION
DETECTOR VERSION
LLM PROVIDER
LLM MODEL
INFERENCE MODE
CORPUS VERSION
PROMPT VERSION
RETRY COUNTS
ARTIFACT HASHES
```

Any field that is not actually recorded must say:

> not recorded

Never infer it.

---

## 21. Reproducibility block

Every investigation view should expose a compact reproducibility panel.

Example:

```text
INVESTIGATION
inv-70207e0ffd15

MODULE
syn-mod-0042

MODEL
iforest-v1-syn-sic-pc-dev-001-s20260922

DATASET
syn-sic-pc-dev-001

FEATURE VERSION
v1

DETECTOR VERSION
v1

ALGORITHM
isolation_forest

CONTAMINATION
0.10

RANDOM STATE
20260922

SPLIT
lot_holdout

CORPUS
1.0.0 · evidence · 360 chunks

LLM
openrouter / <model>

INFERENCE
real / mocked

PROMPT
m9-v1

RETRIES
evidence / hypothesis / report

ARTIFACT HASHES
6 M7/M8 hashes
```

The UI must explain that deterministic components are reproducible while LLM reasoning may differ between runs.

Never claim bit-for-bit reproducibility of a real LLM investigation.

---

## 22. The five epistemic registers

This is a core visual rule.

The same visual treatment must never be used for a measured signal and an LLM hypothesis.

### DATA

Contains:

- signal samples;
- cycle numbers;
- counts;
- anomaly scores;
- anomaly flags.

Treatment:

```text
plain analytical surface
mono values
DATA label where necessary
```

### CALCULATION

Contains:

- deterministic tool outputs;
- M8 metrics;
- thresholds.

Treatment:

```text
left rule
CALCULATED label
slightly raised analytical surface
```

### RETRIEVED EVIDENCE

Contains:

- source passages;
- citations;
- page ranges;
- evidence metadata.

Treatment:

```text
quotation treatment
citation footer
RETRIEVED EVIDENCE label
```

### LLM REASONING

Contains:

- candidate mechanisms;
- reasoning;
- model-assigned confidence;
- hypothesis status.

Treatment:

```text
distinct container
LLM label
provider/model in monospace
```

### VALIDATION

Contains:

- gate outcomes;
- issues;
- retry counts;
- routing decisions.

Treatment:

```text
PASSED / REJECTED gate
issue count
```

Additional registers:

```text
GROUND TRUTH
SYNTHETIC — EVALUATION ONLY

HUMAN DECISION
AWAITING ENGINEER REVIEW
```

Every value-rendering component must declare its register.

---

## 23. Visual language

The product should feel like scientific/engineering software.

Use:

- dark analytical neutral base;
- restrained cool structural accent;
- semantic colours only for state;
- subtle 1 px borders;
- dense technical layout;
- monospace machine identifiers and measurements;
- tabular numerals;
- small uppercase field labels;
- strong but compact hierarchy.

Avoid:

- hero sections;
- marketing copy;
- decorative gradients;
- neon/cyberpunk effects;
- glow;
- excessive rounding;
- giant KPI cards;
- chat bubbles as the main UI;
- "AI-powered" marketing language;
- decorative animations.

The interface should look engineered rather than decorated.

---

## 24. Colour semantics

Colour is never sufficient by itself.

Every state must also have text and, where useful, shape/border treatment.

Important states:

```text
clean
sporadic
persistent

CANDIDATE
SUPPORTED
CONTRADICTED
AMBIGUOUS
INSUFFICIENT_EVIDENCE

COMPLETED
PARTIAL
FAILED

PASSED
REJECTED

REAL INFERENCE
MOCKED INFERENCE

SYNTHETIC GROUND TRUTH
AWAITING ENGINEER REVIEW
```

Red is reserved for system failure and validation rejection.

An anomaly is not a confirmed failure and should not be presented like an alarm condition.

---

## 25. Layout system

Desktop-first.

Primary target:

```text
1440–2560 px
```

Full support:

```text
1280 px
```

Below 1024 px:

- stack read-only panels;
- show a viewport notice;
- preserve scientific content;
- do not design mobile-first.

Use:

- 4 px base spacing;
- 8 px rhythm;
- split/resizable panels;
- sticky context rail;
- dense tables;
- progressive disclosure.

Use a summary-first pattern:

```text
SUMMARY ROW
    ↓
EXPAND
    ↓
FULL INPUT / OUTPUT / PROVENANCE
```

Do not force every detail onto the first viewport.

---

## 26. Scientific visualisation rules

Every chart must answer an engineering question.

Required:

- named axes;
- cycle number as the shared x-axis;
- independent y-scales where quantities differ;
- synchronized hover;
- anomaly markers;
- statistical-baseline markers;
- healthy-reference overlays only from the declared reference artifact;
- exact tooltip values;
- null gaps;
- explicit downsampling state;
- zero-crossing axes for signed metrics.

Forbidden:

- gauges;
- donuts;
- 3D charts;
- unexplained dual axes;
- decorative sparklines;
- confidence bands not provided by the backend;
- browser-computed trend lines;
- browser-computed fits;
- invented change-point markers;
- invented acceptance-limit markers.

---

## 27. The canonical demonstration journey

Demonstration mode must use real stored artifacts.

Default:

```text
Module: syn-mod-0042
Investigation: inv-70207e0ffd15
```

The walkthrough should follow exactly this story:

```text
1. Select canonical module
        ↓
2. Inspect 8 signal trajectories
        ↓
3. Inspect M7 anomaly behaviour
        ↓
4. Inspect M8 detector evaluation
        ↓
5. Explain negative timing honestly
        ↓
6. Open / run investigation
        ↓
7. Inspect Investigation Agent
        ↓
8. Inspect 40 deterministic results
        ↓
9. Inspect Evidence Agent
        ↓
10. Open retrieved evidence
        ↓
11. Inspect Hypothesis Agent
        ↓
12. Compare five candidate mechanisms
        ↓
13. Inspect hypothesis validation
        ↓
14. Inspect Report Agent
        ↓
15. Inspect report validation
        ↓
16. Open Engineering Report
        ↓
17. Trace a claim to evidence
        ↓
18. Trace evidence to source document
```

The canonical case must explicitly teach:

```text
ground truth: healthy
M7 module prediction: no anomaly at module level
statistical baseline: flags
observation-level status: sporadic
LLM candidate: gate_related / SUPPORTED
```

The UI must explain that this is a demonstration of:

> anomaly ≠ failure

rather than presenting the LLM candidate as a physical failure diagnosis.

---

## 28. Investigation launch UX

The only state-creating action is:

> Run Investigation

Never label it:

> AI Analysis

Before launch, show an explicit confirmation dialog:

```text
RUN INVESTIGATION

MODULE
...

MODEL
...

DATASET
...

MAX EVIDENCE
...

LLM PROVIDER
...

LLM MODEL
...

INFERENCE MODE
REAL / MOCKED

This action creates a new investigation record.
Existing investigations are not overwritten.

[Cancel]
[Run Investigation]
```

If an investigation already exists for the same module/model pair:

```text
Existing investigation found.

[Open Existing]
[Run New Investigation]
```

Do not silently create duplicates.

---

## 29. Live investigation behaviour

Never fake progress.

If the backend only knows:

```text
PENDING
```

show:

> Investigation accepted. Stages will appear when backend provenance is available.

Do not animate a stage from 10% → 20% → 30% unless the backend actually provides that state.

When real accumulated provenance exists, show the actual completed/current stages.

If a live run is not available, the interface must degrade to replay mode honestly.

---

## 30. Failure and empty states

These states must never look interchangeable:

```text
NO DATA
NO ANOMALY
INSUFFICIENT EVIDENCE
SYSTEM ERROR
PARTIAL
MOCKED INFERENCE
VALIDATION REJECTED
```

### Missing artifacts

Show a Pipeline Readiness panel:

```text
ARTIFACT             STATUS
features             PRESENT / ABSENT
scores               PRESENT / ABSENT
evaluation           PRESENT / ABSENT
model                PRESENT / ABSENT
healthy reference    PRESENT / ABSENT
knowledge base       PRESENT / ABSENT
LLM                  READY / NOT CONFIGURED
```

Include the expected path and producing CLI when known.

This is a setup state, not a generic error.

### No anomaly

Show:

> No observation exceeded the detector threshold for this module.

Also show:

- observation count;
- anomaly rate;
- threshold;
- baseline comparator.

Never show a blank chart.

### Insufficient evidence

Use explicit language.

Do not imply that the hypothesis is false.

### System error

Show the error without destroying already loaded context.

### Partial investigation

Show:

```text
PARTIAL
```

and identify failed stages.

Completed stages remain inspectable.

---

## 31. Network and API behaviour

Every panel should have its own loading/error/empty state.

Errors must not clear the persistent module context.

Use layout-preserving loading skeletons.

Use retry controls where appropriate.

Never expose API keys in the browser or API responses.

---

## 32. Interaction vocabulary

Use only these primary action verbs:

```text
Select
Inspect
Run Investigation
Compare
Trace
Review
Export
```

Avoid vague buttons such as:

```text
Analyze
Ask AI
Magic
Predict
Fix
Diagnose
```

The UI should make the operation's semantics explicit.

---

## 33. Export

Supported:

```text
JSON — Investigation Record
JSON — Report
JSON — Deterministic Results
JSON — Provenance
Markdown — Report
```

Do not offer PDF unless the backend actually implements it.

Every export must retain:

- investigation id;
- module id;
- model id;
- dataset id;
- created timestamp;
- provenance;
- synthetic-data label.

---

## 34. Accessibility

Requirements:

- WCAG AA contrast;
- no state by colour alone;
- text labels on every state;
- shape/dash differences for chart series;
- visible keyboard focus;
- full keyboard navigation;
- accessible chart descriptions;
- tabular data view for charts;
- semantic headings;
- semantic landmarks;
- `prefers-reduced-motion`;
- no motion carrying meaning.

Charts must remain interpretable without relying on colour.

---

## 35. Frontend implementation rules for the coding agent

The coding agent must follow these rules.

### Rule 1 — Do not invent backend data

If a value does not exist in the backend response:

```text
not recorded
```

Do not fabricate it.

### Rule 2 — Do not perform engineering calculations in React

The frontend does not calculate:

- drift;
- slope;
- thresholds;
- z-scores;
- metrics;
- confidence;
- rankings;
- trend fits.

All displayed numerical results come from the backend.

### Rule 3 — Do not reinterpret epistemic status

Never turn:

```text
HYPOTHESIZED
```

into:

```text
DIAGNOSIS
```

Never turn:

```text
ANOMALY
```

into:

```text
FAILURE
```

Never turn:

```text
MODEL-NOMINATED PRIMARY
```

into:

```text
ROOT CAUSE
```

### Rule 4 — Do not collapse the agentic workflow

The following must remain separately visible:

```text
Investigation Agent
Evidence Agent
Hypothesis Agent
Report Agent
Hypothesis Validation
Report Validation
```

### Rule 5 — Never hide the LLM boundary

The user must be able to see exactly where generative reasoning occurs.

The UI should make this distinction obvious:

```text
DETERMINISTIC
    ↓
RETRIEVAL
    ↓
LLM REASONING
    ↓
VALIDATION
```

### Rule 6 — Never hide mocked inference

Mocked inference receives a persistent banner:

> Mocked inference: no model-generated reasoning.

### Rule 7 — Never create a winner

Candidate mechanisms are competing explanations.

No winner card.

No global confidence ranking.

No composite score.

### Rule 8 — Preserve backend terminology

Use the exact backend vocabulary for enums.

Do not replace:

```text
CANDIDATE
SUPPORTED
CONTRADICTED
AMBIGUOUS
INSUFFICIENT_EVIDENCE
```

with arbitrary UI synonyms.

### Rule 9 — Every claim can be traced

Important values and findings need a `Trace` affordance.

### Rule 10 — Design for the judge

A first-time visitor should understand the engineering workflow without opening source code.

---

## 36. Recommended workspace structure

A strong default route structure:

```text
/
  Mission Control

/modules
  Module Explorer

/modules/[moduleId]
  Module Context

/modules/[moduleId]/signals
  Signal Analysis

/modules/[moduleId]/anomaly
  M7 Anomaly Detection

/modules/[moduleId]/evaluation
  M8 Detector Evaluation

/investigations/[investigationId]
  Investigation Workspace

/investigations/[investigationId]/trace
  Pipeline Trace

/investigations/[investigationId]/evidence
  Evidence Explorer

/investigations/[investigationId]/hypotheses
  Hypothesis Comparison

/investigations/[investigationId]/report
  Engineering Report

/investigations/[investigationId]/provenance
  Provenance Inspector

/history
  Investigation History

/system/readiness
  Pipeline Readiness
```

Routes are a recommendation for frontend organisation; backend API contracts remain defined by `design.md`.

---

## 37. Component architecture

Suggested reusable primitives:

```text
AppShell
ContextRail
MissionFlow
Panel
SplitPanel
SectionHeader
StatusChip
RegisterBadge
MonoId
MetricValue
TraceButton
ProvenanceLink
StageNode
StageInspector
GateResult
EvidenceRecord
HypothesisCard
FindingBlock
ScientificChart
AccessibleDataTable
EmptyState
ErrorState
LoadingState
ReadinessPanel
ReproducibilityBlock
```

Every value-rendering primitive should require:

```ts
register
```

No value should silently inherit an epistemic treatment.

---

## 38. What the first viewport must communicate

On a normal 1440 px desktop viewport, the user should be able to see:

```text
SMARTESS
Scientific Reliability Investigation

MODULE CONTEXT
module / lot / dataset / data origin / detector status

WORKFLOW
DATA → M7 → M8 → INVESTIGATION → EVIDENCE → HYPOTHESES → VALIDATION → REPORT

CURRENT INVESTIGATION
status / investigation id

SIGNAL / DETECTOR SUMMARY
small but real scientific context

NEXT ACTION
Inspect / Open Investigation / Run Investigation
```

The first viewport should answer:

> What am I looking at?

> What has SmartESS already done?

> Where does the agentic investigation happen?

> What can I inspect next?

---

## 39. What must never happen visually

Never produce a frontend where:

- the first screen is a marketing hero;
- the user sees "AI-powered" before seeing the data context;
- M9 appears to be a chatbot;
- deterministic calculations and LLM reasoning look identical;
- the LLM hypothesis is visually presented as a diagnosis;
- one hypothesis is styled as the winner;
- anomaly means failure;
- negative lead time is framed as early warning;
- synthetic ground truth looks like model output;
- mocked inference looks like real inference;
- evidence distance becomes a relevance percentage;
- a blank panel is used for a meaningful "no data" or "no evidence" state;
- validation gates are hidden;
- provenance is relegated to developer-only tooling;
- progress is simulated;
- backend values are recomputed in the browser;
- unsupported capabilities are presented as available.

---

## 40. Definition of done

The frontend is successful only if an experienced reliability engineer opening SmartESS for the first time can identify from the interface alone:

```text
✓ domain contracts / module context
✓ versioned feature engineering
✓ 8 measured engineering signals
✓ M7 anomaly detector
✓ M8 detector evaluation
✓ deterministic engineering analysis
✓ RAG evidence retrieval
✓ verified technical sources
✓ four agent stages
✓ LLM reasoning boundary
✓ competing hypotheses
✓ hypothesis validation gate
✓ report synthesis
✓ report validation gate
✓ uncertainty
✓ engineering report
✓ end-to-end provenance
✓ reproducibility identity
```

The strongest acceptance test is a five-minute screen-share walkthrough in which a judge can follow:

```text
MODULE
  ↓
SIGNALS
  ↓
ANOMALY
  ↓
DETECTOR EVALUATION
  ↓
INVESTIGATION AGENT
  ↓
ENGINEERING CALCULATIONS
  ↓
EVIDENCE AGENT
  ↓
VERIFIED SOURCES
  ↓
HYPOTHESIS AGENT
  ↓
COMPETING MECHANISMS
  ↓
VALIDATION
  ↓
REPORT AGENT
  ↓
REPORT VALIDATION
  ↓
ENGINEERING REPORT
  ↓
PROVENANCE → SOURCE
```

If the judge can understand that chain without reading the repository, the frontend is communicating the actual SmartESS system rather than merely displaying its outputs.

---

## 41. Relationship to `design.md`

`design.md` remains authoritative for:

- backend contracts;
- API requirements;
- artifact semantics;
- M1–M9 immutability;
- exact data values;
- provenance semantics;
- failure states;
- validation behaviour;
- scientific visualisation constraints;
- implementation phases;
- acceptance criteria.

This document is the UX interpretation layer.

If a visual idea conflicts with scientific semantics in `design.md`, scientific semantics win.

If a UI component requires data that `design.md` says does not exist, the component must not fabricate that data.

If an implementation capability is marked `[M10 REQUIREMENT]` in `design.md`, the frontend must show it only after the corresponding backend capability exists, unless the UI explicitly labels it as unavailable/not implemented.

---

## 42. Final design principle

SmartESS should not make the user believe:

> "An AI looked at my module and told me the answer."

It should make the user understand:

> "SmartESS measured and analysed the module, evaluated a frozen detector, ran deterministic engineering calculations, retrieved traceable technical evidence, used an LLM to generate competing mechanisms, validated those hypotheses and the resulting report, and lets me trace every important claim back through the investigation to its evidence."

That distinction is the core of the frontend.

---

## 43. Toolchain decisions

Binding implementation decisions. These are transcribed from the project owner's instruction and are
not open to reinterpretation by the implementing agent.

| Concern | Decision |
| --- | --- |
| Framework | Next.js **App Router** |
| Language | TypeScript |
| Package manager | **npm** |
| Styling | Tailwind CSS with **CSS custom properties** for the SmartESS design tokens (§44) |
| Component library | **None.** Do not introduce a component library that imposes a different visual language |
| State / data fetching | **Plain `fetch` through a typed API client layer** |
| Charting | Recharts (per `tech-stack.md`), subject to §26 |

Explicitly forbidden unless a concrete requirement appears later and is agreed:

```text
Redux
Zustand
TanStack Query
SWR
any other global-state or data-fetching abstraction
```

### Component convention

```text
frontend/
  app/                  App Router route composition (§36)
  components/           reusable primitives (§37, §43.1)
  features/<feature>/   domain-specific components grouped by feature
  lib/api/              typed API client layer (plain fetch)
  lib/types/            generated/hand-mirrored backend types
  styles/               token definitions as CSS custom properties
```

* Reusable primitives live in `components/`.
* Domain-specific components are grouped by feature.
* Route composition happens under the App Router.

### 43.1 Canonical primitive names

The §37 names are **canonical, not placeholders**. The authoritative set is the union of §37 and the
owner-specified list:

```text
AppShell            ContextRail         MissionFlow
Panel               SplitPanel          SectionHeader
RegisterValue       RegisterBadge       StatusChip
MonoId              MetricValue         TraceButton
ProvenanceLink      StageNode           StageInspector
GateResult          EvidenceRecord      HypothesisCard
FindingBlock        ScientificChart     AccessibleDataTable
EmptyState          ErrorState          LoadingState
ReadinessPanel      ReproducibilityBlock
```

`RegisterValue` renders a single value in its epistemic register; `RegisterBadge` renders the register
label itself. Both are required — §37 listed only `RegisterBadge`.

Every value-rendering primitive takes a **required** `register` prop. No value silently inherits an
epistemic treatment.

### 43.2 Backend consumption rules

* Consume only `GET /health`, `POST /investigations`, `GET /investigations`,
  `GET /investigations/{id}`, `GET /investigations/{id}/report` — the endpoints that exist.
* Every other surface — module, telemetry, anomaly, evaluation, evidence, corpus, provenance —
  remains an explicit readiness/unavailable state until its real contract exists (§41, `design.md`
  §10.2).
* Build against typed contracts and adapters, but **never fabricate a backend response**. No mock
  server, no fixture masquerading as live data, no placeholder numbers.
* Stored canonical artifacts may be used only when labelled as demo/replay data per §27.

---

## 44. Concrete design tokens

Tokens are declared once as CSS custom properties and consumed through Tailwind theme extension.
No component hard-codes a colour, spacing or type value.

All colour pairings target **WCAG AA** and must be verified during implementation; any pair failing
AA is corrected in the token, never worked around in a component.

### 44.1 Surfaces, borders, text

```css
:root {
  /* dark analytical neutral base */
  --ss-bg-base:        #0C0F13;
  --ss-bg-surface:     #12161B;
  --ss-bg-raised:      #171C22;
  --ss-bg-inset:       #0A0D10;

  --ss-border-subtle:  #232A32;
  --ss-border-strong:  #313A45;
  --ss-border-width:   1px;

  --ss-text-primary:   #E4E9EF;
  --ss-text-secondary: #A8B2BE;
  --ss-text-muted:     #6F7B88;
  --ss-text-label:     #8793A0;
}
```

### 44.2 Structural accent

One restrained cool accent, for interactive affordances only. It carries no epistemic meaning.

```css
:root {
  --ss-accent:       #4C8DBF;
  --ss-accent-hover: #5FA0D2;
  --ss-accent-muted: #21384A;
  --ss-focus-ring:   #6FB3E0;   /* ≥3:1 against all surfaces */
}
```

### 44.3 Semantic state

Semantic colour is used **only** for state (§24), and never alone — each state below names the text
label and shape treatment that must accompany it.

```css
:root {
  --ss-state-neutral:          #8793A0;
  --ss-state-attention:        #C9922F;
  --ss-state-attention-strong: #D9741F;
  --ss-state-pass:             #3F8F6B;
  --ss-state-reject:           #C0453C;
}
```

| State | Colour | Text label | Shape |
| --- | --- | --- | --- |
| `clean` | neutral | `CLEAN` | plain chip |
| `sporadic` | attention | `SPORADIC` + anomaly rate | plain chip |
| `persistent` | attention-strong | `PERSISTENT` + anomaly rate | plain chip |
| `CANDIDATE` | neutral | `CANDIDATE` | outlined chip |
| `SUPPORTED` | pass | `SUPPORTED` | filled chip |
| `CONTRADICTED` | reject | `CONTRADICTED` | struck chip |
| `AMBIGUOUS` | attention | `AMBIGUOUS` | outlined chip + ambiguity glyph |
| `INSUFFICIENT_EVIDENCE` | muted | `INSUFFICIENT EVIDENCE` | muted chip |
| `COMPLETED` | pass | `COMPLETED` | filled chip |
| `PARTIAL` | attention-strong | `PARTIAL` | **dashed** chip |
| `FAILED` | reject | `FAILED` | filled chip |
| `PASSED` | pass | `PASSED` | gate chip |
| `REJECTED` | reject | `REJECTED` + issue count | gate chip |

`--ss-state-reject` (red) is reserved for **system failure and validation rejection only**. An
anomaly never uses it: `sporadic` and `persistent` are analytically emphasised, not alarmed.

### 44.4 Register tokens

Register differentiation is **primarily structural** — rule, surface elevation, quotation, label —
not chromatic. The single exception is LLM REASONING, which carries a restrained hue because §Rule 5
requires the generative boundary to be unmissable.

```css
:root {
  --ss-reg-data-surface:        var(--ss-bg-surface);

  --ss-reg-calc-surface:        var(--ss-bg-raised);
  --ss-reg-calc-rule:           var(--ss-border-strong);   /* 2px left rule */

  --ss-reg-evidence-surface:    #11171C;
  --ss-reg-evidence-rule:       #2C3A44;                   /* quotation rule */

  --ss-reg-llm-surface:         #171526;
  --ss-reg-llm-border:          #3A3357;
  --ss-reg-llm-accent:          #8E7BC4;

  --ss-reg-validation-surface:  var(--ss-bg-raised);

  --ss-reg-groundtruth-border:  #4A4436;                   /* + hatched fill */
  --ss-reg-mocked-border:       #6B5E2E;                   /* + hatched fill */
  --ss-reg-human-border:        #313A45;                   /* dashed outline */
}
```

Hatching for GROUND TRUTH and MOCKED INFERENCE is a 4 px repeating diagonal at 12 % opacity, so the
state survives greyscale and colour-blind rendering.

### 44.5 Spacing

4 px base, 8 px rhythm.

```css
:root {
  --ss-space-1:  4px;   --ss-space-2:  8px;   --ss-space-3: 12px;
  --ss-space-4: 16px;   --ss-space-5: 20px;   --ss-space-6: 24px;
  --ss-space-8: 32px;   --ss-space-12: 48px;
}
```

### 44.6 Typography

```css
:root {
  --ss-font-sans: ui-sans-serif, system-ui, "Inter", "Helvetica Neue", Arial, sans-serif;
  --ss-font-mono: ui-monospace, "JetBrains Mono", "SFMono-Regular", Menlo, monospace;

  --ss-text-label-size:   11px;  /* uppercase, letter-spacing 0.06em */
  --ss-text-body-size:    13px;
  --ss-text-value-size:   13px;  /* mono, tabular-nums */
  --ss-text-section-size: 15px;
  --ss-text-title-size:   18px;

  --ss-leading-tight: 1.25;
  --ss-leading-body:  1.5;
  --ss-measure-prose: 80ch;
}
```

Monospace with `font-variant-numeric: tabular-nums` is **mandatory** for: `module_id`, `test_id`,
`lot_id`, `dataset_id`, `model_id`, `investigation_id`, `evidence_id`, `chunk_id`, `document_id`,
`candidate_id`, cycle numbers, scores, metrics, thresholds, hashes, enum values, tool names, file
paths, and provider/model strings.

Field labels are small, uppercase, letter-spaced and low-emphasis; the value carries the emphasis.

### 44.7 Radius and elevation

```css
:root {
  --ss-radius-sm: 2px;
  --ss-radius-md: 3px;
}
```

Minimal rounding. Structure comes from 1 px borders and the technical grid — **no shadows**, no glow,
no gradients.

### 44.8 Chart tokens

```css
:root {
  --ss-chart-grid: #1E242B;
  --ss-chart-axis: #55616E;

  --ss-signal-rds-on:          #6FA8DC;
  --ss-signal-vth:             #93C47D;
  --ss-signal-igss:            #E0A458;
  --ss-signal-idss:            #C98AC9;
  --ss-signal-vds-on:          #7FC3C0;
  --ss-signal-electrical-power:#B8A46A;
  --ss-signal-tj:              #E08A7A;
  --ss-signal-tc:              #8FA0C4;

  --ss-marker-anomaly:        #D9741F;
  --ss-marker-baseline-flag:  #4C8DBF;
  --ss-reference-band:        #2A323A;
}
```

Each of the eight signal series must additionally be distinguishable by **dash pattern or marker
shape**, so series identity survives greyscale (§34). Anomaly markers and statistical-baseline
markers use different shapes, not only different hues.

### 44.9 State copy

Exact strings. These must never be reworded into each other.

```text
NO DATA
  title:  ARTIFACT NOT AVAILABLE
  body:   This artifact has not been generated in this environment.
  detail: expected path + producing CLI
  note:   This is a setup state, not an error.

NO ANOMALY
  title:  NO ANOMALY DETECTED
  body:   No observation exceeded the detector threshold for this module.
  detail: observation count · anomaly rate · threshold · baseline comparator

NOT APPLICABLE
  title:  NOT APPLICABLE
  body:   <verbatim backend note>
  detail: Timing is defined only for detected positives.

ANALYSIS NOT PERFORMED
  title:  ANALYSIS NOT PERFORMED
  body:   This calculation was not run for this investigation.
  detail: <recorded limitation> + producing CLI

NO EVIDENCE
  title:  KNOWLEDGE BASE NOT INGESTED
  body:   No evidence records are available, so no citation can be resolved.
  detail: scripts/ingest_knowledge.py

INSUFFICIENT EVIDENCE
  title:  INSUFFICIENT EVIDENCE
  body:   The retrieved evidence cannot discriminate this mechanism.
  note:   This does not mean the mechanism is false.

MECHANISM UNRESOLVED
  title:  ANOMALY DETECTED — MECHANISM UNRESOLVED
  body:   No candidate mechanism was proposed for this investigation.

REASONING UNAVAILABLE
  title:  LLM REASONING UNAVAILABLE
  body:   The hypothesis stage did not complete.
  detail: <verbatim backend error>

MOCKED INFERENCE
  title:  MOCKED INFERENCE
  body:   No model-generated reasoning. This investigation ran without a configured LLM provider.

VALIDATION REJECTED
  title:  VALIDATION REJECTED
  body:   <issue count> issue(s) recorded by the <gate name> gate.

PARTIAL
  title:  PARTIAL
  body:   One or more stages did not complete. Completed stages remain inspectable.
  detail: failed stage names

SYSTEM ERROR
  title:  SYSTEM ERROR
  body:   The request failed. Module context is preserved.
  detail: status code + <detail> from the API

CAPABILITY NOT IMPLEMENTED
  title:  NOT IMPLEMENTED
  body:   This capability does not exist in the current backend.
  detail: design.md reference
```

### 44.10 Token discipline

* No component may hard-code a hex value, px value or font stack.
* Tailwind is configured to expose these tokens; arbitrary values are not used for anything the
  tokens cover.
* Adding a token requires adding it here first.
