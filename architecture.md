# BurnInGuard AI — Architecture

## 1. Document Purpose

BurnInGuard AI is an agentic reliability-intelligence platform for SiC MOSFET power modules used in EV power electronics.

The platform is designed to detect abnormal degradation during reliability testing, investigate potential failure mechanisms using engineering evidence, and generate an evidence-backed engineering report.

The architecture is configurable at the module level. A manufacturer can define or upload the specifications of its SiC module, test conditions, monitored parameters, and acceptance limits. The system adapts the data-processing and ML workflow to the supplied configuration.

The initial implementation is focused on SiC power modules. The architecture deliberately separates reusable platform services from SiC-specific reliability knowledge.

---

## 2. Architectural Goals

The system shall:

1. Accept configurable SiC module profiles.
2. Support different voltage, current, topology, and parameter specifications.
3. Ingest historical and test-time telemetry.
4. Validate telemetry against the selected module profile.
5. Prepare and quality-check reliability data.
6. Train and evaluate component-specific ML models.
7. Detect anomalous degradation before conventional limits are necessarily violated.
8. Analyze temporal degradation trajectories.
9. Compare devices against healthy population behavior.
10. Investigate candidate failure mechanisms using deterministic tools.
11. Retrieve supporting technical evidence from a curated reliability knowledge base.
12. Keep hypotheses distinct from confirmed physical failures.
13. Generate traceable engineering reports.
14. Preserve experiment, model, dataset, and evidence provenance.
15. Allow the architecture to support additional SiC module profiles without rewriting the core platform.

---

## 3. Architectural Principles

### 3.1 Configuration-driven

Component specifications must not be hard-coded into the ML pipeline.

The module profile defines the component and test context.

### 3.2 Component-specific learning

The system must not assume that one ML model is valid for every SiC module.

A model is trained and evaluated against the relevant component population and telemetry.

### 3.3 Evidence before hypothesis

The agent must obtain quantitative evidence before proposing a failure mechanism.

### 3.4 Hypothesis is not confirmation

The system may identify a mechanism as a candidate explanation, but it must not claim physical failure without appropriate evidence.

### 3.5 Deterministic tools for engineering calculations

Numerical analysis, statistical calculations, drift calculations, and threshold checks should be implemented as deterministic tools.

LLMs orchestrate and explain these tools rather than replacing them.

### 3.6 Human-in-the-loop

Final reliability and failure-analysis decisions remain with the engineer.

BurnInGuard provides decision support, not certification or autonomous failure disposition.

### 3.7 Provenance

Every model result and engineering hypothesis should be traceable to telemetry, calculations, configuration, and supporting sources.

---

# 4. High-Level Architecture

```text
                         BURNINGUARD AI
                               |
        +----------------------+----------------------+
        |                      |                      |
        v                      v                      v
  Module Profile         Telemetry/Data        Reliability KB
     Layer                  Layer                  Layer
        |                      |                      |
        +----------------------+----------------------+
                               |
                               v
                       Data Intelligence
                               |
                 +-------------+-------------+
                 |                           |
                 v                           v
          Feature Engineering        Data Quality Engine
                 |                           |
                 +-------------+-------------+
                               |
                               v
                       ML Intelligence
                               |
                 +-------------+-------------+
                 |                           |
                 v                           v
         Anomaly Detection          Degradation Analysis
                 |                           |
                 +-------------+-------------+
                               |
                               v
                       Agentic Orchestrator
                               |
          +--------------------+--------------------+
          |                    |                    |
          v                    v                    v
   Analysis Tools      Evidence Retrieval     Hypothesis Engine
          |                    |                    |
          +--------------------+--------------------+
                               |
                               v
                     Engineering Report
                               |
                               v
                       Engineer Review
```

---

# 5. Logical System Layers

The platform is divided into the following logical layers:

1. Presentation Layer
2. API and Application Layer
3. Configuration Layer
4. Data Ingestion Layer
5. Data Intelligence Layer
6. ML Intelligence Layer
7. Agentic Intelligence Layer
8. Reliability Knowledge Layer
9. Reporting Layer
10. Persistence and Infrastructure Layer

---

# 6. Presentation Layer

The frontend provides the engineering interface.

Primary responsibilities:

- Project creation
- Module profile creation
- Datasheet upload
- Profile verification
- Dataset upload
- Test configuration
- Data-quality visualization
- Model training status
- Model metrics
- Anomaly visualization
- Component trajectory visualization
- Agent investigation status
- Evidence display
- Engineering report visualization

The UI should distinguish clearly between:

- measured values
- model predictions
- statistical findings
- agent hypotheses
- confirmed user decisions

The interface must never present an agent hypothesis as a confirmed physical failure.

---

# 7. Module Profile Layer

The Module Profile is the central configuration object.

It describes:

```text
Component identity
Electrical specifications
Thermal specifications
Stress conditions
Health parameters
Acceptance criteria
Source documents
```

Example:

```json
{
  "technology": "SiC MOSFET",
  "topology": "half_bridge",
  "voltage_class_V": 1200,
  "current_rating_A": 600,
  "health_parameters": [
    "RDS_on",
    "Vth",
    "IGSS",
    "Tj"
  ]
}
```

The values above are illustrative only.

Production values must come from the manufacturer's datasheet, test configuration, or verified engineering input.

---

# 8. Datasheet Processing

A manufacturer may upload a datasheet instead of manually entering every specification.

The workflow is:

```text
Datasheet PDF
     |
     v
Document Extraction
     |
     v
Specification Extraction Agent
     |
     v
Candidate Module Profile
     |
     v
Profile Validator
     |
     v
Engineer Confirmation
     |
     v
Validated Module Profile
```

The extraction agent may identify:

- voltage rating
- current rating
- gate-voltage limits
- temperature limits
- electrical characteristics
- thermal characteristics
- relevant test information

Extracted values are candidates until verified.

---

# 9. Telemetry Ingestion Layer

Telemetry can originate from:

- CSV
- Parquet
- JSON
- database exports
- laboratory test systems
- future live instrumentation interfaces

The first implementation should prioritize file-based ingestion.

The ingestion pipeline is:

```text
Uploaded Dataset
      |
      v
Schema Detection
      |
      v
Column Mapping
      |
      v
Unit Validation
      |
      v
Data Type Validation
      |
      v
Missing-Value Analysis
      |
      v
Range Validation
      |
      v
Normalized Dataset
```

No model should train on data that has failed mandatory validation.

---

# 10. Telemetry Model

Telemetry represents observations over the lifetime or stress history of a module.

Typical fields include:

```text
module_id
lot_id
timestamp
cycle_number

VDS
VGS
ID

Tj
Tc
Ta
delta_Tj

RDS_on
Vth
IGSS
IDSS
VDS_on
VF
Rth
```

Not every module provides every parameter.

The Module Profile defines which parameters are available and which are critical.

---

# 11. Data Quality Engine

The Data Quality Engine checks:

- missing values
- duplicate records
- invalid timestamps
- impossible values
- unit mismatches
- unexpected ranges
- sensor discontinuities
- abnormal sampling intervals
- inconsistent module identifiers
- inconsistent test stages

The engine produces a quality report before ML training.

Example:

```text
Dataset Quality
----------------------------
Rows:                 1,240,000
Modules:              2,000
Missing values:       0.7%
Duplicate rows:       0
Invalid temperatures: 3
Schema status:        PASS
```

The system should block training when critical quality conditions fail.

---

# 12. Feature Engineering Layer

Feature engineering converts raw telemetry into reliability indicators.

Potential features include:

### Temporal features

- absolute change
- percentage change
- slope
- rate of change
- rolling mean
- rolling variance
- acceleration of drift
- cycle-to-cycle change

### Population features

- z-score relative to healthy population
- percentile position
- lot deviation
- distance from population centroid

### Cross-parameter features

- RDS(on) versus Tj
- Tj versus load current
- Vth versus temperature
- IGSS versus stress duration
- thermal rise versus electrical resistance

### Reliability features

- cumulative stress
- thermal-cycle count
- temperature swing
- estimated degradation rate
- time-to-threshold

Feature definitions should be stored with the experiment metadata.

---

# 13. Synthetic Data Architecture

BurnInGuard requires a controlled development dataset for SiC reliability research.

The simulator should not generate arbitrary random rows.

It should generate trajectories based on:

```text
Module Profile
+
Stress Profile
+
Healthy Population Model
+
Manufacturing Variation
+
Physics-Informed Relationships
+
Failure Mechanism Model
+
Measurement Noise
```

Output:

```text
Virtual Module Population
        |
        +-- Healthy modules
        +-- Bond-wire degradation
        +-- Die-attach / solder degradation
        +-- Gate-related degradation
        |
        v
Time-series telemetry
```

The synthetic dataset is for controlled evaluation and prototype development.

It must not be presented as measured production data.

---

# 14. Failure Mechanism Layer

The initial SiC implementation focuses on a limited set of mechanisms.

### Bond-wire / interconnect degradation

Potential observable behavior:

- RDS(on) increase
- VDS,on increase
- increased conduction loss
- associated thermal changes

### Die-attach / solder degradation

Potential observable behavior:

- thermal impedance increase
- abnormal junction-temperature rise
- increased thermal resistance
- possible electrical degradation

### Gate-oxide / gate-related degradation

Potential observable behavior:

- Vth shift
- IGSS increase
- IDSS changes
- associated electrical performance changes

These relationships must be supported by technical literature or manufacturer documentation.

They are not hard-coded as absolute diagnostic rules.

---

# 15. ML Intelligence Layer

The ML layer is responsible for:

1. Learning normal population behavior.
2. Detecting anomalous modules.
3. Quantifying degradation.
4. Predicting future drift where sufficient data exists.
5. Supporting failure-mode classification where labels are available.

Candidate models may include:

- Isolation Forest
- One-Class SVM
- Autoencoders
- Random Forest
- Gradient Boosting
- XGBoost
- temporal models
- regression models
- survival/degradation models

The model-selection process should be data-driven.

The system should not force one algorithm onto every dataset.

---

# 16. Model Training Workflow

```text
Validated Dataset
       |
       v
Dataset Profiling
       |
       v
Train / Validation / Test Split
       |
       v
Feature Engineering
       |
       v
Candidate Model Training
       |
       v
Evaluation
       |
       v
Model Selection
       |
       v
Model Registry
```

Splits should preferably occur at module or lot level rather than randomly splitting individual time-series rows.

This prevents leakage between the same physical component's training and test observations.

---

# 17. ML Evaluation

Metrics depend on the task.

Anomaly detection:

- precision
- recall
- F1
- false-positive rate
- false-negative rate
- detection lead time

Regression/degradation prediction:

- MAE
- RMSE
- R²
- prediction error over time

Classification:

- precision
- recall
- F1
- confusion matrix

The system should also evaluate whether anomalies are detected early enough to be operationally useful.

---

# 18. Model Registry

Each trained model should store:

```text
model_id
profile_id
dataset_id
feature_version
algorithm
training_time
training_data_version
evaluation_metrics
configuration
status
```

Models are associated with a specific module profile.

A model trained for one component configuration must not silently be reused for another incompatible configuration.

---

# 19. Agentic Intelligence Layer

The agentic layer is responsible for orchestrating engineering analysis.

It should use specialized tools instead of attempting to perform all numerical reasoning inside an LLM.

Core agents:

### Configuration Agent

Processes datasheets and configuration information.

### Data Preparation Agent

Inspects and prepares uploaded telemetry.

### Model Engineering Agent

Coordinates model training and evaluation.

### Investigation Agent

Investigates detected anomalies.

### Evidence Retrieval Agent

Retrieves supporting reliability literature and technical documentation.

### Hypothesis Agent

Maps observed signatures to candidate failure mechanisms.

### Report Agent

Produces the final engineering report.

A central orchestrator controls the workflow.

---

# 20. Agent Orchestration

Example workflow:

```text
Anomaly Detected
      |
      v
Investigation Agent
      |
      +--> Trajectory Analyzer
      |
      +--> Population Comparator
      |
      +--> Thermal Analyzer
      |
      +--> Electrical Correlation Analyzer
      |
      +--> Evidence Retrieval
      |
      v
Hypothesis Agent
      |
      v
Evidence Verification
      |
      v
Engineering Report
```

The agent should be able to decide which tools are relevant based on the observed anomaly.

---

# 21. Deterministic Analysis Tools

The tool registry should expose controlled engineering functions.

Examples:

```text
calculate_drift()
calculate_slope()
calculate_percent_change()
compare_population()
calculate_z_score()
analyze_temperature_dependence()
detect_change_point()
calculate_correlation()
estimate_degradation_rate()
check_acceptance_limits()
retrieve_failure_evidence()
```

Each tool should return structured output.

Example:

```json
{
  "parameter": "RDS_on",
  "initial_value": 18.2,
  "current_value": 21.4,
  "change_percent": 17.58,
  "population_percentile": 98.7
}
```

The agent interprets the result but does not fabricate the calculation.

---

# 22. Reliability Knowledge Base

The knowledge base contains structured engineering evidence.

Primary source categories:

1. Automotive reliability standards.
2. Peer-reviewed semiconductor reliability research.
3. Manufacturer application notes.
4. Manufacturer reliability documentation.
5. Manufacturer datasheets.

Potential sources include:

- AQG 324
- AEC-Q101 where applicable
- IEEE research
- Infineon documentation
- Wolfspeed documentation
- ROHM documentation
- onsemi documentation
- STMicroelectronics documentation

The source hierarchy should be preserved in the database.

---

# 23. Evidence Record

Each knowledge-base entry should contain:

```text
evidence_id
failure_mechanism
component_type
observable_signature
conditions
engineering_interpretation
recommended_investigation
source_type
source_title
source_url
publication_date
page_or_section
confidence
```

Example:

```text
Failure mechanism:
Bond-wire degradation

Observable signatures:
RDS(on) increase
VDS,on increase

Recommended investigation:
Electrical characterization
Physical inspection

Source:
Peer-reviewed reliability study
```

The actual values and relationships must be populated from verified sources.

---

# 24. Retrieval-Augmented Investigation

The Evidence Retrieval Agent uses the observed signature to retrieve relevant evidence.

Example:

```text
Observed:
RDS(on) ↑
Tj rise ↑
```

Retrieval:

```text
       ↓
Failure-mode index
       ↓
Bond-wire evidence
Die-attach evidence
Thermal-path evidence
       ↓
Relevant sources
```

The agent then compares the retrieved evidence against the measured telemetry.

---

# 25. Hypothesis Engine

The Hypothesis Agent should produce ranked candidate hypotheses internally, but the user-facing report should clearly identify them as hypotheses.

Example:

```text
Candidate mechanism:
Bond-wire degradation

Supporting evidence:
- RDS(on) increased by X%
- increase occurred progressively
- behavior deviates from healthy population
- literature associates similar electrical behavior
  with package/interconnect degradation

Confidence:
Moderate

Status:
Unconfirmed hypothesis
```

The agent must also identify contradictory evidence.

This prevents confirmation bias in the investigation workflow.

---

# 26. Evidence-Bound Reporting

The final report should separate:

### Observed

Direct measurements and calculated quantities.

### Detected

ML/statistical findings.

### Hypothesized

Potential failure mechanisms.

### Supported by

Technical sources and retrieved evidence.

### Recommended

Potential follow-up investigations.

### Confirmed

Only information explicitly confirmed by the engineer or an appropriate physical test.

This distinction is mandatory for reliability credibility.

---

# 27. Engineering Report Structure

A report should contain:

```text
1. Component Information
2. Test Configuration
3. Data Quality
4. Observed Degradation
5. Anomaly Analysis
6. Model Results
7. Candidate Failure Mechanisms
8. Supporting Evidence
9. Recommended Investigation
10. Limitations
11. Model Information
12. Source References
```

The report should be exportable as PDF and JSON.

---

# 28. Human-in-the-Loop Workflow

BurnInGuard does not automatically make final manufacturing decisions.

```text
BurnInGuard
    |
    v
Detect
    |
    v
Investigate
    |
    v
Recommend
    |
    v
Engineer
    |
    v
Accept / Reject / Investigate Further
```

Engineer feedback can optionally be stored for later model improvement.

---

# 29. Data Model

Core entities:

```text
User
Project
ModuleProfile
TestProfile
Dataset
DatasetVersion
TelemetryRecord
FeatureSet
Experiment
Model
Prediction
Anomaly
Investigation
EvidenceRecord
Hypothesis
EngineeringReport
```

Relationships:

```text
Project
  |
  +-- ModuleProfile
  |
  +-- TestProfile
  |
  +-- Dataset
  |      |
  |      +-- DatasetVersion
  |
  +-- Experiment
         |
         +-- Model
         +-- Prediction
         +-- Anomaly
         +-- Investigation
                |
                +-- Evidence
                +-- Hypothesis
                +-- Report
```

---

# 30. Storage Architecture

Recommended logical stores:

### Relational database

Store:

- users
- projects
- profiles
- datasets metadata
- experiments
- models
- predictions
- investigations
- reports
- source metadata

### Object storage

Store:

- uploaded datasheets
- raw datasets
- processed datasets
- model artifacts
- generated reports

### Vector database

Store embeddings of:

- technical papers
- application notes
- reliability documents
- datasheets
- internal engineering documentation

The vector database supports semantic evidence retrieval.

---

# 31. API Layer

The backend should expose APIs for:

```text
/projects
/modules
/modules/{id}/profile
/modules/{id}/datasheet
/datasets
/datasets/{id}/validate
/experiments
/experiments/{id}/train
/models
/anomalies
/investigations
/investigations/{id}
/evidence
/reports
```

Long-running operations such as training and investigation should execute asynchronously.

---

# 32. Processing Architecture

Long-running workflows should be separated from synchronous API requests.

```text
Frontend
   |
   v
FastAPI
   |
   +--> PostgreSQL
   |
   +--> Object Storage
   |
   +--> Task Queue
            |
            +--> Data Worker
            +--> ML Worker
            +--> Agent Worker
            +--> Report Worker
```

For the prototype, these workers can initially run within a simpler application architecture.

The interfaces should remain modular so the system can be distributed later.

---

# 33. Security and Isolation

The system should treat manufacturer data as sensitive.

Requirements:

- authenticated access
- project-level authorization
- encrypted data transfer
- controlled file uploads
- isolated processing
- no cross-project dataset access
- audit logs
- source provenance
- model version tracking

Manufacturer datasets must never be used for another project's training without explicit authorization.

---

# 34. Frontend Architecture

Recommended frontend sections:

```text
Dashboard
|
+-- Projects
|
+-- Module Profiles
|     +-- Specifications
|     +-- Datasheet
|     +-- Test Configuration
|
+-- Datasets
|     +-- Upload
|     +-- Quality
|     +-- Exploration
|
+-- Models
|     +-- Training
|     +-- Evaluation
|     +-- Registry
|
+-- Monitoring
|     +-- Module Health
|     +-- Anomalies
|     +-- Trajectories
|
+-- Investigations
|     +-- Evidence
|     +-- Hypotheses
|     +-- Tools
|
+-- Reports
```

---

# 35. Backend Architecture

The backend can be organized into domain services:

```text
backend/
|
+-- api/
|   +-- projects
|   +-- modules
|   +-- datasets
|   +-- experiments
|   +-- models
|   +-- investigations
|   +-- reports
|
+-- domain/
|   +-- module_profiles
|   +-- telemetry
|   +-- reliability
|   +-- investigations
|
+-- ml/
|   +-- preprocessing
|   +-- features
|   +-- anomaly_detection
|   +-- degradation
|   +-- evaluation
|   +-- registry
|
+-- agents/
|   +-- orchestrator
|   +-- configuration
|   +-- data
|   +-- model
|   +-- investigation
|   +-- evidence
|   +-- hypothesis
|   +-- reporting
|
+-- knowledge/
|   +-- ingestion
|   +-- retrieval
|   +-- citations
|
+-- workers/
|
+-- storage/
|
+-- tests/
```

---

# 36. End-to-End Workflow

```text
1. Engineer creates project
              |
2. Engineer uploads SiC module datasheet
              |
3. Configuration Agent extracts specifications
              |
4. Engineer verifies profile
              |
5. Engineer defines reliability test
              |
6. Telemetry is uploaded
              |
7. Data Preparation Agent validates dataset
              |
8. Features are generated
              |
9. Model Engineering Agent trains candidate models
              |
10. Models are evaluated on held-out modules/lots
              |
11. Best valid model is registered
              |
12. Telemetry is analyzed
              |
13. Anomaly is detected
              |
14. Investigation Agent begins investigation
              |
15. Numerical tools analyze trajectory
              |
16. Evidence Retrieval Agent retrieves literature
              |
17. Hypothesis Agent evaluates candidate mechanisms
              |
18. Report Agent creates engineering report
              |
19. Engineer reviews findings
              |
20. Engineer makes final decision
```

---

# 37. Reference Architecture for the AGENTX Prototype

For the hackathon, the implementation should remain manageable.

```text
Next.js Frontend
       |
       v
FastAPI Backend
       |
       +-------------------+
       |                   |
       v                   v
PostgreSQL            Object Storage
       |
       +-------------------+
       |
       v
ML Pipeline
       |
       v
Agent Orchestrator
       |
       +---- Analysis Tools
       |
       +---- Reliability Knowledge Base
       |
       +---- Evidence Retrieval
       |
       +---- Hypothesis Engine
       |
       v
Engineering Report
```

A full distributed infrastructure is not necessary for the prototype.

---

# 38. Prototype Scope

The AGENTX implementation should demonstrate:

1. SiC module profile creation.
2. Datasheet-assisted configuration.
3. Synthetic or validated telemetry ingestion.
4. Data-quality analysis.
5. ML anomaly detection.
6. Progressive degradation visualization.
7. Agentic investigation.
8. Evidence retrieval.
9. Failure-mechanism hypothesis generation.
10. Evidence-backed report generation.

The prototype should focus on depth rather than claiming complete industrial qualification.

---

# 39. Future Expansion

The architecture can later support:

- additional SiC module configurations
- IGBT modules
- discrete SiC MOSFETs
- additional reliability tests
- real-time instrumentation
- laboratory hardware integration
- digital-twin calibration
- federated learning
- manufacturer-specific models
- predictive remaining-useful-life estimation
- automated test-plan generation
- integration with manufacturing execution systems

These are future capabilities, not requirements for the initial AGENTX implementation.

---

# 40. Core Architectural Principle

BurnInGuard should be understood as:

```text
                CONFIGURABLE PLATFORM
                         |
                 SiC Module Profile
                         |
              Component-specific Data
                         |
                 Component-specific ML
                         |
                  Agentic Investigation
                         |
               Evidence-backed Reasoning
                         |
                 Engineering Decision
```

The platform is reusable.

The reliability model is component- and dataset-specific.

The engineering evidence is domain-specific.

The final decision remains human-controlled.

---

# 41. Architecture Summary

BurnInGuard AI combines four major capabilities:

**Configuration**

Understand the specific SiC module and its test requirements.

**Machine Learning**

Detect abnormal behavior and degradation trajectories.

**Agentic Investigation**

Autonomously select analytical tools, investigate anomalies, and connect observations to candidate failure mechanisms.

**Evidence Retrieval**

Ground hypotheses in standards, peer-reviewed research, manufacturer documentation, and verified technical sources.

The resulting system moves from:

```text
Pass / Fail
```

toward:

```text
Observe
→ Detect
→ Analyze
→ Investigate
→ Explain
→ Recommend
→ Engineer decides
```

This is the intended architecture for the AGENTX BurnInGuard AI implementation.
