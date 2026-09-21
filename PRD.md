# BurnInGuard AI — Product Requirements Document

Product: BurnInGuard AI
Domain: SiC MOSFET power-module reliability for EV power electronics.
Purpose: detect abnormal degradation and support evidence-based reliability investigation.
Primary output: traceable engineering report.
Product type: configurable agentic reliability-intelligence platform.
Initial deployment: research/hackathon prototype.
Production certification is explicitly out of scope.

1. Product Vision

Traditional screening primarily checks whether measured values exceed predefined limits.
BurnInGuard additionally evaluates behavioral deviation and degradation trajectories.
Core question: is the module behaving abnormally before conventional limits are violated?
Second question: what evidence supports the observed anomaly?
Third question: which failure mechanisms are plausible?
Fourth question: what should an engineer investigate next?
BurnInGuard assists engineers; it does not replace physical failure analysis.

2. Problem Statement

EV power modules operate under electrical, thermal, and mechanical stress.
Reliability tests collect electrical and thermal measurements over time.
Simple limit checks can miss gradual degradation while values remain within specification.
Relevant indicators include RDS(on), Vth, IGSS, IDSS, VDS(on), Tj, Tc, and Rth.
Abnormal trajectories may provide earlier warning than absolute limit violations.
BurnInGuard detects such behavior and investigates its possible causes.
Problem statement: detect, quantify, investigate, and explain abnormal SiC module degradation.

3. Scope

Primary domain: SiC MOSFET power modules.
Application domain: EV power electronics.
Initial reliability focus: accelerated reliability and power-cycling analysis.
Supported module specifications are user-configurable.
The platform must not assume one manufacturer.
The platform must not assume one voltage class.
The platform must not assume one current rating.
The platform must not assume one package.
The platform must not assume one parameter set.
Models remain component- and dataset-specific.
Architecture is reusable; physical behavior is not assumed universal.

4. Target Users

Reliability engineers investigate anomalous components and degradation.
Test engineers configure tests and validate telemetry.
Failure-analysis engineers prioritize physical characterization.
Quality engineers review screening and investigation results.
Engineering managers review reliability trends and reports.

5. User Goals

Create a project.
Create or upload a SiC module profile.
Upload a manufacturer datasheet.
Extract candidate specifications.
Verify extracted specifications.
Configure a reliability test.
Upload historical or experimental telemetry.
Validate data quality.
Train component-specific models.
Evaluate models on held-out data.
Detect anomalous behavior.
Launch an agentic investigation.
Retrieve technical evidence.
Review candidate failure mechanisms.
Generate and export an engineering report.

6. End-to-End Workflow

Create project.
Create or extract Module Profile.
Validate Module Profile.
Configure Test Profile.
Upload telemetry.
Validate dataset.
Prepare features.
Train candidate models.
Evaluate models.
Register valid model.
Detect anomalies.
Launch Investigation Agent.
Run deterministic analysis tools.
Retrieve reliability evidence.
Evaluate candidate hypotheses.
Generate report.
Engineer reviews and decides.

7. Module Profile Requirements

The Module Profile is the central configuration object.
It defines component identity.
It defines electrical specifications.
It defines thermal specifications.
It defines stress conditions.
It defines monitored health parameters.
It defines conventional acceptance criteria.
It records source documents.
The profile must be versioned.

8. Component Identity

technology
topology
manufacturer
part_number
voltage_class
current_rating
package
module_id
Manufacturer and part number may be optional.
Sensitive identifiers should not be mandatory for the prototype.

9. Electrical Specification Requirements

Support VDS maximum.
Support VGS maximum.
Support VGS ON.
Support VGS OFF.
Support ID maximum.
Support switching frequency.
Support operating electrical ranges.
Distinguish absolute maximum ratings.
Distinguish recommended operating conditions.
Distinguish typical characteristics.
Distinguish guaranteed limits.
Do not invent missing values.

10. Thermal Specification Requirements

Support Tj maximum.
Support Tc maximum.
Support Ta range.
Support Rth(j-c) when available.
Support thermal impedance when available.
Support cooling configuration when relevant.
Temperature must be represented explicitly in analysis.
Temperature-sensitive electrical parameters require temperature-aware interpretation.

11. Test Profile

Test Profile defines how the module is stressed.
Support Power Cycling.
Support HTOL.
Support HTGB.
Support HTRB.
Support HTFB.
Support Dynamic Gate Stress.
Support Custom Reliability Test.
Do not assume every test targets the same failure mechanism.
Power-cycling fields may include VDS, ID, Tj minimum, Tj maximum, delta Tj, cycle count, cycle duration, heating duration, cooling duration, and switching frequency.
Actual values must come from verified test specifications.

12. Health Parameters

Support RDS(on).
Support Vth.
Support IGSS.
Support IDSS.
Support VDS(on).
Support VF.
Support Tj.
Support Tc.
Support Ta.
Support Rth.
Support VDS.
Support VGS.
Support ID.
Not every module must provide every parameter.
Pipeline behavior must adapt to the active parameter set.

13. Acceptance Criteria

Allow maximum RDS(on).
Allow maximum RDS(on) drift.
Allow Vth range.
Allow maximum IGSS.
Allow maximum temperature.
Allow maximum thermal resistance.
Acceptance limits are separate from anomaly thresholds.
A module can pass conventional limits while remaining behaviorally abnormal.

14. Datasheet-Assisted Configuration

Users may upload a manufacturer datasheet.
Document extraction identifies candidate specifications.
Configuration Agent constructs a candidate profile.
Profile Validator checks units and consistency.
Engineer confirms critical values.
Only confirmed values become active configuration.
Every extracted value should retain source location when available.
Conflicting values must be surfaced rather than silently resolved.

15. Telemetry Ingestion

Initial formats: CSV.
Initial formats: JSON.
Initial formats: Parquet.
Initial formats: database exports.
Future versions may support laboratory instruments.
Future versions may support live test-bench telemetry.
Prototype priority is reliable file-based ingestion.
Telemetry may contain module_id, lot_id, timestamp, cycle_number, VDS, VGS, ID, Tj, Tc, Ta, delta_Tj, RDS(on), Vth, IGSS, IDSS, VDS(on), VF, and Rth.
Actual fields depend on the Module Profile.

16. Data Validation

Validate schema compatibility.
Validate required columns.
Validate data types.
Validate units.
Validate timestamps.
Detect missing values.
Detect duplicate records.
Detect invalid values.
Validate module and lot identifiers.
Check sampling intervals.
Check expected physical ranges.
Dataset status must be PASS, WARNING, or BLOCKED.
BLOCKED datasets cannot enter model training.
Raw data must remain unchanged.

17. Data Provenance

Record source dataset.
Record project.
Record Module Profile version.
Record Test Profile version.
Record transformation history.
Record feature version.
Record validation result.
Record dataset version.
Record upload metadata.
Every downstream result must reference the exact dataset version.

18. Feature Engineering

Calculate absolute parameter change.
Calculate percentage change.
Calculate slope.
Calculate rate of change.
Calculate rolling mean.
Calculate rolling variance.
Detect change points.
Calculate population z-score.
Calculate population percentile.
Calculate population distance.
Calculate lot deviation.
Analyze RDS(on) versus Tj.
Analyze Tj versus ID.
Analyze Vth versus temperature.
Analyze IGSS versus stress duration.
Analyze thermal rise versus electrical resistance.
Feature definitions must be versioned.

19. ML Objectives

Objective 1: anomaly detection.
Objective 2: degradation quantification.
Objective 3: future drift prediction where data supports it.
Objective 4: failure-mode classification where labeled data and evidence support it.
Not every dataset must support every objective.

20. ML Training

Profile the validated dataset.
Create train, validation, and test splits.
Prevent temporal leakage.
Prefer module-level or lot-level splits.
Construct features.
Train candidate models.
Evaluate candidates.
Select an appropriate model.
Register the model.
Record preprocessing configuration.
Record hyperparameters.
Record dataset and feature versions.
Candidate algorithms may include Isolation Forest, One-Class SVM, Autoencoder, Random Forest, Gradient Boosting, XGBoost, regression, and temporal models.
Algorithm choice must depend on the task and data.

21. ML Evaluation

Anomaly metrics may include precision, recall, F1, false-positive rate, and false-negative rate.
Detection lead time should be measured when supported.
Regression metrics may include MAE, RMSE, and R2.
Classification metrics may include precision, recall, F1, and confusion matrix.
Early-warning performance should be measured where appropriate.
No universal accuracy claim is permitted before the dataset and task are fixed.

22. Model Registry

Store model_id.
Store module_profile_id.
Store dataset_version.
Store feature_version.
Store algorithm.
Store hyperparameters.
Store training timestamp.
Store evaluation metrics.
Store status.
Store artifact location.
Models for incompatible profiles must not be silently reused.

23. Core Detection Principle

Datasheet compliance is not equivalent to behavioral normality.
BurnInGuard evaluates absolute compliance.
BurnInGuard evaluates population behavior.
BurnInGuard evaluates temporal trajectory.
Example: healthy RDS(on) may move 18.0 to 18.4 mΩ.
An abnormal module might move 18.0 to 21.0 mΩ.
An absolute 25 mΩ limit could still classify that module as passing.
BurnInGuard can nevertheless flag the abnormal trajectory.

24. Synthetic Dataset

A controlled synthetic dataset is required for development.
It must represent trajectories, not independent random rows.
Simulator inputs include Module Profile.
Simulator inputs include Stress Profile.
Simulator inputs include Healthy Population Model.
Simulator inputs include Manufacturing Variation.
Simulator inputs include Physics-Informed Relationships.
Simulator inputs include Failure Mechanism Model.
Simulator inputs include Measurement Noise.
Output is time-series module telemetry.
Synthetic data must never be represented as production telemetry.

25. Synthetic Population

Generate healthy modules.
Generate degrading modules.
Generate multiple lots.
Include manufacturing variation.
Include measurement noise.
Include sensor variation.
Include different stress histories.
Each virtual module receives an individual trajectory.
Simulator retains hidden ground truth for evaluation.
Unsupervised anomaly models must not receive hidden failure labels.

26. Initial Failure Mechanisms

Initial scope includes bond-wire/interconnect degradation.
Initial scope includes die-attach/solder degradation.
Initial scope includes gate-oxide/gate-related degradation.
Mechanisms must be grounded in technical evidence.
The prototype must not attempt to model every SiC failure mechanism.

27. Bond-Wire Degradation

Potential signature: RDS(on) increase.
Potential signature: VDS(on) increase.
Potential signature: increased conduction loss.
Potential signature: associated thermal rise.
Degradation should be progressive where appropriate.
Mathematical behavior must be justified by technical evidence.

28. Die-Attach/Solder Degradation

Potential signature: thermal impedance increase.
Potential signature: thermal resistance increase.
Potential signature: junction-temperature rise.
Potential signature: secondary electrical degradation.
Simulator should represent thermal-path effects.
Exact relationships require supporting evidence.

29. Gate-Related Degradation

Potential signature: Vth shift.
Potential signature: IGSS increase.
Potential signature: IDSS change.
Potential signature: electrical performance change.
Simulator should represent progressive degradation.
Exact relationships require supporting evidence.

30. Synthetic Ground Truth

Simulator knows module state.
Simulator knows degradation state.
Simulator knows injected mechanism.
Simulator knows stress history.
ML models infer behavior from observable telemetry.
Ground truth is retained for evaluation.
Each dataset records simulation version.
Each dataset records random seed.
Each dataset records parameter assumptions.
Each dataset records mechanism model.
Each dataset records source references.

31. Real Dataset Strategy

Public real semiconductor datasets may validate general anomaly-detection machinery.
Real datasets must not be relabeled as SiC power-module burn-in data when they are not.
Real-data results and synthetic SiC results must remain separate.
Real data validates general analytics.
Controlled synthetic data supports SiC-specific degradation experiments.
Production-level SiC reliability cannot be claimed without representative real SiC data and appropriate validation.

32. Reliability Knowledge Base

Knowledge base stores engineering evidence.
Primary source category: reliability standards.
Primary source category: peer-reviewed research.
Primary source category: manufacturer technical documentation.
Primary source category: manufacturer datasheets.
Additional source category: institutional technical reports.
Secondary sources are lower priority.
Potential standards include AQG 324.
AEC-Q101 may be used where applicable.
Potential manufacturer sources include Infineon, Wolfspeed, ROHM, onsemi, and STMicroelectronics.

33. Evidence Records

Store evidence_id.
Store failure_mechanism.
Store component_type.
Store observable_signature.
Store stress_condition.
Store engineering_interpretation.
Store recommended_investigation.
Store source_type.
Store source_title.
Store source_url.
Store publication_date.
Store page_or_section.
Store evidence_strength.
Evidence chain: observation → supporting evidence → interpretation.
Never encode observation → guaranteed failure.

34. Agentic System

Orchestrator Agent controls workflow.
Configuration Agent processes specifications.
Data Preparation Agent validates telemetry.
Model Engineering Agent trains and evaluates models.
Investigation Agent analyzes anomalies.
Evidence Retrieval Agent retrieves technical sources.
Hypothesis Agent evaluates candidate mechanisms.
Report Agent generates the engineering report.
Agents use deterministic engineering tools whenever possible.

35. Configuration Agent

Process datasheets.
Extract specifications.
Normalize units.
Create candidate profiles.
Identify ambiguities.
Request engineer confirmation.
Never invent missing engineering values.

36. Data Preparation Agent

Inspect uploaded data.
Validate schema.
Identify data problems.
Normalize units.
Prepare model-ready data.
Produce data-quality report.
Preserve raw data and transformation history.

37. Model Engineering Agent

Profile datasets.
Select candidate models.
Run reproducible experiments.
Evaluate model performance.
Register validated models.
Reject models that fail defined criteria.

38. Investigation Agent

Inspect anomaly trajectories.
Compare with healthy populations.
Calculate drift and rate-of-change.
Analyze temperature effects.
Analyze correlated parameters.
Select relevant tools.
Request evidence.
Consider multiple mechanisms.
Search contradictory evidence.
State when evidence is insufficient.

39. Deterministic Tools

calculate_drift().
calculate_slope().

## Condensed Continuation
The following requirements complete the product definition and acceptance boundary.
BurnInGuard AI is a configurable agentic reliability-intelligence platform for SiC MOSFET power modules.
It accepts manufacturer-defined module specifications, test conditions, and telemetry.
It validates data and trains component-specific ML models.
It detects abnormal degradation and launches investigation workflows.
Agents use deterministic engineering tools and curated technical evidence.
Agents connect observed electrical and thermal signatures to candidate physical mechanisms.
The system produces a traceable engineering report.
The report contains observations, calculations, model findings, hypotheses, evidence, recommendations, and limitations.
BurnInGuard does not replace reliability engineers or physical failure analysis.
Its purpose is faster, systematic, explainable, and evidence-based reliability investigation.
Initial AGENTX implementation focuses on SiC EV power modules.
The architecture remains configurable for different SiC module specifications.

Appendix A — Core Data Objects

Project: owns module profiles, tests, datasets, experiments, investigations, and reports.
ModuleProfile: describes the component and its engineering limits.
TestProfile: describes stress type and test conditions.
Dataset: identifies raw or processed telemetry.
DatasetVersion: immutable version of a dataset.
FeatureSet: versioned derived features.
Experiment: records one model-training/evaluation run.
Model: registered trained artifact.
Prediction: model output for a module or observation.
Anomaly: detected abnormal behavior.
Investigation: agentic analysis of an anomaly.
EvidenceRecord: source-backed technical evidence.
Hypothesis: candidate failure mechanism.
EngineeringReport: final traceable investigation output.

Appendix B — Core Engineering Distinctions

Acceptance limit means a predefined specification boundary.
Anomaly means statistically or behaviorally unusual data.
Degradation means measurable change in health-related behavior.
Prediction means a model-derived estimate.
Hypothesis means a candidate physical explanation.
Confirmation means evidence sufficient for engineering validation.
BurnInGuard must preserve these distinctions throughout the UI and backend.

Appendix C — Agent Boundaries

Orchestrator controls sequence and prerequisites.
Configuration Agent controls profile extraction.
Data Preparation Agent controls dataset preparation.
Model Engineering Agent controls ML experiments.
Investigation Agent controls analytical investigation.
Evidence Retrieval Agent controls source retrieval.
Hypothesis Agent controls candidate mechanism reasoning.
Report Agent controls final report composition.
No agent may bypass global evidence and safety rules.

Appendix D — MVP Priorities

Priority 1: configurable SiC Module Profile.
Priority 2: reliable telemetry ingestion and validation.
Priority 3: literature-grounded synthetic dataset.
Priority 4: anomaly detection and degradation analysis.
Priority 5: deterministic engineering tools.
Priority 6: curated reliability knowledge base.
Priority 7: agentic investigation.
Priority 8: evidence-backed engineering report.
Priority 9: polished AGENTX demonstration.
Hardware integration remains optional for MVP.

