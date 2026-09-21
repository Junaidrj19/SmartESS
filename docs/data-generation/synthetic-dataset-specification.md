# Synthetic Dataset Specification (M4-A)

**Status:** specification complete; generator not implemented.  
**Milestone:** M4-A (design only). Implementation is M4-B.  
**Data origin:** all generated telemetry must be labeled `data_origin: synthetic`. It must never be presented as real semiconductor production telemetry.  
**Simulation claim boundary:** this document defines a **semi-synthetic, physics-informed, configurable simulator**. It is **not** a validated physical reliability model, not a digital twin of a specific manufacturer part, and not an estimate of field failure rates.

Labeling used throughout:

| Label | Meaning |
| --- | --- |
| **Physical fact** | Established engineering relationship stated at a qualitative level. Not a fitted device model. |
| **Engineering evidence** | Relationship supported by a verified external source (datasheet, standard, paper, manufacturer note). **No such sources are cited in this document** because none have been ingested and verified in-repo. |
| **Simulation assumption** | Chosen so the generator produces useful, controllable trajectories. Not measured manufacturing data. |
| **Mathematical approximation** | Convenient functional form (linear, exponential, additive Gaussian). Domain-limited. |
| **Synthetic ground truth** | Latent labels injected by the simulator for evaluation only. Not an observable and not a physical confirmation. |

---

## 1. Purpose

The first synthetic dataset exists so SmartESS can develop and evaluate, under known conditions:

1. Telemetry schema conformance and data-quality handling  
2. Feature engineering, including temperature conditioning  
3. Anomaly detection (population and trajectory)  
4. Degradation detection and severity scoring  
5. Investigation workflows (signature vs competing hypotheses)  
6. Model evaluation with **held-out** modules/lots and **detection lead time**

It is not a substitute for laboratory characterization. Unsupervised models must not be trained on ground-truth mechanism labels.

---

## 2. Scope

### In scope (first generator configuration)

| Axis | First configuration |
| --- | --- |
| Device class | 1200 V-class **SiC MOSFET** power modules |
| Topology | **half-bridge** |
| Test | **power cycling** (`TestProfile.test_type = power_cycling`) |
| Type profile | Illustrative ModuleProfile `sic-ref-half-bridge-illustrative` |
| Stress profile | Illustrative TestProfile `pc-sic-ref-illustrative-001` |
| Temporal grain | **Cycle-level** trajectories (one observation per configured cycle stride) |
| Mechanisms | Healthy; bond-wire/interconnect; die-attach/thermal-path; gate-related |

Reference configuration objects (placeholders, not manufacturer facts):

- `examples/module-profiles/sic-reference-module.json`
- `examples/test-profiles/power-cycling-reference.json`

### Out of scope for the first dataset

- Other semiconductor technologies (Si IGBT, GaN, etc.)
- Other topologies as first-class populations (single-switch, full-bridge may be added later)
- HTOL, HTGB, HTRB, HTFB, dynamic gate stress as first generator modes
- Package-level 3D FEM, electro-thermal co-simulation, or SPICE
- Wear-out physics calibrated to a specific OEM qualification
- High-frequency within-cycle switching waveforms (ns–µs)
- Claiming validated lifetime (e.g. Coffin–Manson, LESIT) predictions
- Mixing generated files with `data_origin: real`

The pipeline architecture (stages, config, provenance) must remain extensible so later configurations can add tests and module types without rewriting telemetry contracts.

---

## 3. Dataset philosophy

1. **Semi-synthetic:** ModuleProfile and TestProfile supply type-level electrical/thermal/stress **configuration**. Trajectories are simulated, not recorded from a rack.
2. **Physics-informed, not physics-validated:** qualitative thermal/electrical coupling is used; equations are approximations with stated domains.
3. **Configurable and reproducible:** identical configuration + seed + generator version → identical artifacts.
4. **Traceable:** dataset metadata records seeds, versions, assumptions, and mechanism models.
5. **Latent vs observed:** the simulator holds a latent physical state; telemetry is a noisy, possibly incomplete observation of that state.
6. **Ground truth is separate:** mechanism and severity never appear on `TelemetryRecord`.
7. **Progressive degradation:** no step-function “at cycle 50,000, RDS(on) jumps.”
8. **Heterogeneous population:** lots, modules, onsets, rates, and stress offsets vary so models cannot memorize one curve.
9. **Temperature ≠ failure:** temperature-driven parameter movement is generated in healthy modules; feature engineering must condition on temperature.
10. **Class mix is a simulation choice:** population fractions are not field prevalence.

---

## 4. Input contracts

The generator **consumes** existing contracts. It must not invent a second ModuleProfile or TestProfile.

```text
ModuleProfile          what the component type is
      +
TestProfile            how the type is stressed
      +
GenerationConfig       population, noise, scenario, seeds (M4-B)
      ↓
Synthetic Dataset      telemetry + ground truth + provenance
```

### 4.1 ModuleProfile (type configuration)

Used as the **nominal type** for the population:

- Identity: technology `SiC MOSFET`, topology `half_bridge`, 1200 V blocking class  
- Electrical typicals/limits used as **anchors** for healthy baselines (RDS(on) at stated Tj, VTH, IGSS/IDSS limits, VGS on/off)  
- Thermal: Tj/Tc ratings, Rth(j-c) typical as the **nominal** thermal resistance  
- Health-parameter names: which channels are in-scope  
- Acceptance criteria: conventional limits for later validation tools — **not** ML thresholds and **not** ground-truth failure

**Simulation assumption:** numeric values on the illustrative profile are placeholders. They define a consistent virtual part family, not a real SKU.

**Instance vs type (no schema change):**

- `ModuleProfile.identity.module_id` is the **type** identifier (e.g. `sic-ref-half-bridge-illustrative`).
- `TelemetryRecord.module_id` is a **physical instance** identifier, unique per virtual module.
- Binding of instance → type is: `TelemetryRecord.test_id` → `TestProfile.module_profile_id` → ModuleProfile, plus dataset metadata `module_profile_id` / `module_profile_version`.
- M3 documentation describes the single-fixture case where instance and type ids coincide. Population datasets must keep them distinct. Telemetry already forbids embedding a ModuleProfile object. **No M1–M3 field is missing** for this binding.

### 4.2 TestProfile (applied stress — single source of truth)

The generator must **read** power-cycling conditions from TestProfile, not duplicate them in GenerationConfig except as **optional small perturbations** around those setpoints.

From the illustrative power-cycling profile (placeholders):

| Field | Illustrative value | Role in simulation |
| --- | --- | --- |
| `electrical_stress.vds` | 400 V | Applied bus / load voltage observation mean |
| `electrical_stress.id` | 300 A | Load current mean |
| `electrical_stress.vgs_on` / `vgs_off` | +15 / −4 V | Gate drive during on/off (cycle-level uses on-state as default) |
| `thermal_stress.tj_minimum` / `tj_maximum` | 40 / 150 °C | Target cycle temperature window |
| `thermal_stress.delta_tj` | 110 °C | Must remain consistent with Tj max−min when all three exist |
| `thermal_stress.tc_minimum` / `tc_maximum` | 35 / 90 °C | Case-temperature window |
| `environmental_conditions.ambient_temperature` | 25 °C | Ta baseline |
| `cycle_profile.target_cycles` | 100000 | Trajectory length (may subsample observations) |
| `cycle_profile.heating_duration_s` / `cooling_duration_s` | 2 / 4 | Used for timestamp spacing and thermal lag, not FEM |
| `measurement_configuration.channels` | RDS_on, VTH, IGSS, Tj, Tc, VDS, VGS, ID | Minimum emitted channels |
| `measurement_configuration.sampling_interval_s` | 1 | **Not** used as “emit one TelemetryRecord per second” (see §15) |

GenerationConfig may add derived telemetry channels allowed by the Telemetry contract (`VDS_on`, `IDSS`, `Rth`, `delta_Tj`, `electrical_power`, `Ta`) even when they are absent from `measurement_configuration`. That is an observation choice, not a second TestProfile.

### 4.3 TelemetryRecord (output observation)

Every emitted row must be a valid `TelemetryRecord` (`schema_version` `1.0.0`):

- UTC timestamps  
- `data_origin: synthetic`  
- `source_type`: `parquet` or `illustrative_reference` as appropriate  
- `dataset_id` set to the generated dataset id  
- `lot_id` set  
- `cycle_number` present and monotonic per module for this test  
- measurements with explicit units and status  
- **no** `ground_truth`, mechanism, anomaly, or prediction fields (already forbidden by the model)

### 4.4 GenerationConfig (conceptual — not implemented in M4-A)

A versioned JSON object (M4-B) that controls population, scenario, sampling, variation, and seeds. It must not restate ModuleProfile datasheet tables or TestProfile stress tables; it **references** their ids and versions.

See §30.

### 4.5 Contract gaps reviewed

| Question | Decision |
| --- | --- |
| Need `module_profile_id` on TelemetryRecord? | **No for M4-A.** Resolvable via TestProfile + dataset metadata. Optional denormalization can be considered later if joins become painful; not required to represent the dataset. |
| Need ground-truth fields on telemetry? | **No.** Explicitly forbidden; separate files. |
| Need `electrical_power` / `delta_Tj` on TestProfile channels? | **No.** Telemetry already allows those parameters. |
| TestProfile `sampling_interval_s = 1` vs cycle-level dataset? | Generator uses `observation_stride_cycles` (GenerationConfig). Do not emit 1 Hz × 100k cycles. Not a schema defect. |

**M1, M2, and M3 contracts are unchanged.**

---

## 5. Population generation

### 5.1 Pipeline stages (do not collapse)

```text
1. Bind type inputs
      ModuleProfile + TestProfile + GenerationConfig
2. Module population
      lots, module ids, scenario class assignment
3. Manufacturing variation
      lot-level offsets + within-lot instance offsets
4. Healthy baseline behavior
      temperature dependence, normal stress response, small temporal jitter
5. Thermal / electrical stress response
      map TestProfile setpoints (+ optional per-module stress offset) to latent power and temperatures
6. Degradation trajectory
      onset, rate, mechanism-specific latent states, progressive stages
7. Measurement / sensor effects
      noise, bias, drift, optional quality defects
8. Emit TelemetryRecord sequence
9. Emit GroundTruth (separate)
10. Write dataset provenance
```

Each stage has one responsibility. Stage 6 must not also apply sensor noise. Stage 7 must not invent new mechanisms. Stage 5 must not copy TestProfile into a parallel stress schema.

### 5.2 Identifiers

| Id | Cardinality | Notes |
| --- | --- | --- |
| `dataset_id` | 1 per generation run | Stable, recorded in telemetry and metadata |
| `lot_id` | `n_lots` | Manufacturing grouping |
| `module_id` | `n_modules` | Physical instance |
| `test_id` | typically 1 per dataset | Same TestProfile for the first configuration |
| `telemetry_id` | 1 per observation | Unique |

### 5.3 Configurable sizes (development defaults ≠ prevalence)

All counts are **GenerationConfig** parameters. The following are **development defaults** for a computationally manageable first run. They are **not** estimates of factory volume or field mix.

| Parameter | Development default | Intent |
| --- | --- | --- |
| `n_modules` | 750 | Inside the 500–1000 development band |
| `n_lots` | 5 | Multiple lots so lot-level splits are possible |
| `modules_per_lot` | 150 | Equal lots by default; config may unbalance |
| `target_cycles` | from TestProfile (100000) | Stress horizon |
| `observation_stride_cycles` | 200 | ~501 observations/module if cycles 0..100000 inclusive of endpoints — order of 4×10^5 rows at 750 modules; scalable |
| `n_modules` scaling | config | Generator must allow 50 (debug) through 10^4+ without code-structure change |

**Simulation assumption:** equal lot sizes.

### 5.4 Variation layers (all modules are not identical)

| Layer | What varies | Why |
| --- | --- | --- |
| Lot-to-lot | Shared offset on baselines (RDS, VTH, Rth, leakages) | Process/material batch effects; lot-level generalization tests |
| Module-to-module | Additional offsets around the lot mean | Unit variation; prevents one deterministic curve |
| Stress | Small offsets on ID, ΔTj, cooling effectiveness | Fixtures and control loops are not identical |
| Temporal (healthy) | Small cycle-to-cycle process + control jitter | Healthy is not a flat line |
| Measurement | Noise, bias, optional defects | Latent ≠ observed |

Without these layers, an ML model can memorize a single trajectory rather than learn population-relative behavior.

---

## 6. Manufacturing variation

### 6.1 Why lot vs module

**Engineering rationale (qualitative physical fact):** wafer/process and assembly lots often share systematic offsets; units within a lot still differ.  

**Why the simulator separates them:** evaluation must be able to ask (a) does the model generalize to a **new lot**? (b) does it generalize to a **new module** in a known lot? A single iid draw per module cannot pose (a).

**Simulation assumption:** lot and module effects are additive in the latent parameter’s natural units (or log-units where noted). Exact industrial σ is unknown and **must not** be presented as measured yield data.

### 6.2 Latent manufacturing parameters

Sampled once per lot and once per module at generation time, then held constant (except degradation and allowed calibration drift).

| Latent parameter | Lot effect | Module effect | Anchor (illustrative profile) | Notes |
| --- | --- | --- | --- | --- |
| `rds_on_ref_mohm` | yes | yes | typical 4.5 mΩ at 25 °C, VGS=15 V | Reference-temperature on-resistance |
| `vth_ref_V` | yes | yes | typical 2.8 V at 25 °C | Threshold at reference T |
| `igss_base_uA` | yes | yes | below maximum 0.5 µA typical-max placeholder | Healthy gate leakage floor |
| `idss_base_uA` | yes | yes | well below 200 µA max placeholder | Healthy drain leakage floor |
| `rth_jc_C_per_W` | yes | yes | typical 0.12 °C/W | Junction-to-case thermal resistance |
| `k_th_coupling` | optional lot | yes | 1.0 | How strongly case tracks junction (cooling effectiveness) |

**Mathematical approximation (defaults, not fab data):** independent Gaussian offsets, truncated to stay physically ordered (positive resistances, VTH inside a wide window). Example **simulation** scales (configurable):

| Offset | Lot σ | Module σ (within lot) |
| --- | --- | --- |
| RDS(on) at T_ref | 0.08 mΩ | 0.05 mΩ |
| VTH at T_ref | 0.08 V | 0.05 V |
| Rth(j-c) | 0.004 °C/W | 0.003 °C/W |
| IGSS base | 0.02 µA | 0.02 µA |
| IDSS base | 5 µA | 5 µA |

These numbers are **mathematical convenience** so variation is visible but smaller than intended degradation amplitudes. They are not Cpk or foundry statistics.

RDS(on) typical at 150 °C on the profile (7.2 mΩ) is **not** a second independent manufacturing draw; it constrains the temperature map (§8).

---

## 7. Healthy behavior

Healthy modules receive **no** injected degradation mechanism. They still move.

A healthy trajectory includes:

1. Manufacturing offsets (constant)  
2. Temperature dependence of electrical parameters  
3. Normal response to the applied power-cycling window (Tj, Tc, ΔTj, ID, VDS)  
4. Small temporal variation: control-loop jitter, minor cycle-to-cycle ΔTj and ID noise  
5. Measurement noise (stage 7)

Healthy modules must **not** be perfectly flat. They must **not** be labeled anomalous in ground truth.

### 7.1 Baseline generation

For each module, at each observation cycle \(c\):

1. Draw or retrieve applied stress for that cycle (TestProfile means + stress jitter).  
2. Compute latent power and temperatures (healthy thermal path).  
3. Compute latent electrical parameters at that Tj (temperature maps only).  
4. Add a small zero-mean temporal process on RDS and VTH (optional AR(1) or white) with amplitude **below** early-degradation slopes.  
5. Apply sensor model.

**Simulation assumption:** healthy temporal process is stationary (no secular wear). Any long-term drift in a “healthy” module would be mislabeled for this first dataset; healthy means **no injected mechanism**, not “zero slope.”

**Mathematical approximation:** healthy extra RDS jitter σ on the order of 0.02 mΩ (configurable), much smaller than measurable-degradation RDS increase.

---

## 8. Temperature effects

### 8.1 Why this section exists

If RDS(on) simply tracks Tj, and degraded modules run hotter, a detector can learn **high temperature = failure**. That is the wrong lesson. The dataset must contain:

- Healthy modules at high Tj with **normal** RDS(on) for that Tj  
- Degraded modules whose RDS(on) **exceeds** the temperature-conditioned healthy expectation  

Later feature engineering **must** provide temperature-conditioned features (see §8.5). The generator does not implement features; it must make those features *possible*.

### 8.2 RDS(on) vs temperature

**Physical fact (qualitative):** in the usual on-state operating range, SiC MOSFET RDS(on) increases as junction temperature increases. The coefficient is device-specific.

**Engineering evidence:** none verified in this repository. The illustrative ModuleProfile lists two **placeholder** typicals (4.5 mΩ at 25 °C and 7.2 mΩ at 150 °C). Those are configuration anchors, not datasheet facts.

**Mathematical approximation (domain: 25–175 °C unless config says otherwise):** linear interpolation/extrapolation in Celsius between the two profile typicals, applied to the **module’s** `rds_on_ref` by scaling the type curve:

\[
R_{\mathrm{DS,on}}(T_j) = r_{\mathrm{ref}} \cdot \frac{R_{\mathrm{type}}(T_j)}{R_{\mathrm{type}}(T_{\mathrm{ref}})}
\]

with \(T_{\mathrm{ref}} = 25\,^{\circ}\mathrm{C}\) and \(R_{\mathrm{type}}\) the piecewise-linear type curve. This is **not** claimed as a universal MOSFET law (real devices can be nonlinear; high-T inversion layers, etc.).

Degradation adds a **residual** on top of this temperature-conditioned value (see §12–14), not a replacement of the temperature map.

### 8.3 VTH vs temperature

**Physical fact (qualitative):** MOSFET threshold voltage typically decreases as temperature increases.

**Simulation assumption:** a configurable linear coefficient \(\alpha_{VTH}\) (default e.g. −2 mV/°C, **not** a measured SiC coefficient). Apply to `vth_ref` relative to 25 °C. Gate-related degradation adds an additional shift **not** explained by this map.

### 8.4 Thermal network (lumped)

**Physical fact (qualitative):** dissipated power raises junction temperature above case; case is coupled to coolant/ambient through a thermal path.

**Mathematical approximation (single-lump, cycle-level, not a Cauer/Foster identification):**

\[
P \approx I_D^{2}\,R_{\mathrm{DS,on}} + P_{\mathrm{sw}}
\]

\[
T_j \approx T_c + P \cdot R_{\mathrm{th,jc}}
\]

\[
T_c \approx T_a + P \cdot R_{\mathrm{th,ca}} + \text{control targeting}
\]

Power cycling **targets** `tj_minimum` / `tj_maximum` from TestProfile. The generator should treat those as **closed-loop setpoints** (as the illustrative TestProfile states) plus configurable tracking error, rather than solving a free-running thermal ODE as the primary driver.

- **Healthy:** observed ΔTj stays near the TestProfile window, with small jitter.  
- **Die-attach / thermal-path degradation:** same control may command similar Tj while **Tc, inferred Rth, and required power/current** change, **or** if control is imperfect, Tj overshoot increases. First configuration: **mixed** — primarily increase latent `Rth` and the Tj−Tc gap; allow modest Tj overshoot (configurable).  

\(P_{\mathrm{sw}}\) is a **simulation constant or weak function of frequency** from TestProfile; switching loss is **not** a validated model.

`delta_Tj` telemetry, when emitted, is derived as \(T_{j,\mathrm{max}}-T_{j,\mathrm{min}}\) over the cycle (or stored peak-to-valley), `origin: derived`.

### 8.5 Temperature normalization requirements (for later features)

The specification **requires** future feature engineering (not M4-B generator) to support at least one of:

1. Residual \(R_{\mathrm{DS,on}} - \hat{R}(T_j)\) using a population or module temperature model  
2. RDS(on) referred to a reference temperature  
3. Explicit features: `Tj`, `Tc`, `delta_Tj`, `RDS_on`, and their joint statistics  

Evaluation of anomaly models **should** report performance on temperature-conditioned features vs raw RDS so “hot = bad” shortcuts are visible.

**Generator obligation:** emit Tj (and Tc when in the channel list) on the same records as RDS(on) for valid samples, except where the data-quality scenario deliberately drops a channel.

---

## 9. Stress effects

TestProfile is the stress contract. GenerationConfig may add:

| Parameter | Meaning |
| --- | --- |
| `stress_id_rel_sigma` | relative σ on ID around TestProfile `id` |
| `stress_delta_tj_sigma_C` | σ on achieved ΔTj around setpoint |
| `stress_vds_sigma_V` | σ on VDS observation/control |

**Simulation assumption:** first dataset uses **one** TestProfile for all modules (same nominal VDS, ID, ΔTj, cycle count). Per-module stress offsets model fixture scatter, not a second test plan.

How stress influences observations:

| Input | Healthy influence | Degradation interaction |
| --- | --- | --- |
| VDS | Observed near setpoint | Weak coupling in first config (not avalanche modeling) |
| ID | Sets conduction loss and RDS extraction conditions | Bond-wire: higher effective RDS → higher conduction loss at same ID |
| VGS | On-state RDS and VTH measurement context | Gate mechanism may shift VTH; RDS map still uses on-state VGS |
| Tj_min / Tj_max / ΔTj | Temperature maps and thermal observations | Thermal-path mechanism changes Rth and Tj−Tc |
| Heating / cooling duration | Timestamp spacing; optional thermal lag | Not a fatigue-law input in v1 (no Coffin–Manson lifetime draw) |
| Cycle count \(c\) | Time index | Degradation state is a function of \(c\) relative to onset |

**Do not** implement a second `electrical_stress` object. Perturbations are GenerationConfig + per-module latent offsets.

**Physical fact (qualitative):** power-cycling ΔTj and cycle time affect interconnect and solder fatigue in real modules.  

**Simulation assumption for v1:** mechanism **assignment and onset** are drawn from GenerationConfig, **not** computed from a verified lifetime equation of ΔTj and \(t_{\mathrm{on}}\). Using LESIT/Coffin–Manson as if calibrated would be an unsupported claim. Optional later: severity **rate** may scale with ΔTj as a labeled simulation knob, still not a qualified life model.

---

## 10. Degradation mechanisms

Initial **simulation categories** (aligned with PRD §26 and architecture §14):

1. `healthy`  
2. `bond_wire_interconnect`  
3. `die_attach_thermal_path`  
4. `gate_related`  

**These are simulation categories. They are not claims about the prevalence, ranking, or exclusivity of real SiC power-module failure mechanisms.** They are not diagnoses. A real module can exhibit mixed or different mechanisms; v1 assigns **one primary injected mechanism** per degrading module (configurable mixed-mechanism later).

ModuleProfile `relevant_failure_mechanisms` are investigation **references**, not generator labels. Ground truth uses the four categories above.

Each mechanism has:

- a **physical rationale** (why an engineer might look at certain channels)  
- a **simulated signature** (what this generator injects)  
- an **evidence status** (unverified in-repo → treat as simulation assumption)

**Candidate signature ≠ confirmed diagnosis.** Anomaly detectors should see correlated channels; investigation tools must still treat mechanism as a hypothesis.

---

## 11. Degradation progression

Degradation is a **state over cycles**, not a single jump.

### 11.1 Stages (synthetic ground truth)

| Stage | Name | Intent |
| --- | --- | --- |
| 0 | `healthy` | Before onset, or never-degrading module |
| 1 | `early` | Residual exists but is comparable to noise / healthy jitter |
| 2 | `measurable` | Temperature-conditioned residual exceeds a configured detectability threshold **in the latent state** (not a claim that every detector will fire) |
| 3 | `advanced` | Large residual; still may remain inside ModuleProfile acceptance limits |
| 4 | `terminal` | Crosses configured terminal criterion (acceptance-style or mechanism-specific); test may continue with flagged state |

Stages are **synthetic ground truth** for lead-time evaluation. They are not JEDEC or AQG 324 failure definitions.

### 11.2 Onset

Each degrading module draws `onset_cycle` independently from a configurable distribution.

**Development default (simulation assumption):** onset uniform on \([c_{\min}, c_{\max}]\) with e.g. \(c_{\min}=5000\), \(c_{\max}=70000\) (inclusive, aligned to stride). Not a Weibull field model.

Before `onset_cycle`, mechanism residual is 0 (healthy maps only).

### 11.3 Rate heterogeneity

Each degrading module draws `rate_scale` (e.g. lognormal, median 1, σ configurable) multiplying the mechanism’s progression speed. **Do not** use one curve for all modules.

### 11.4 Progression shape

**Mathematical approximation:** after onset, a dimensionless damage \(d(c) \in [0,1]\) grows as a power function:

\[
d(c) = \mathrm{clip}\left(\left(\frac{c - c_{\mathrm{onset}}}{c_{\mathrm{span}}}\right)^{p}, 0, 1\right)
\]

with \(p\) configurable (default \(p=1.4\) so growth is faster later — **convenience**, not a fatigue exponent). Residuals scale with \(d(c)\) times mechanism amplitudes times `rate_scale`.

Optional: small additive process noise on \(d\) so paths are not identical given the same onset.

### 11.5 Stage boundaries (configurable)

Defined on a mechanism-specific **severity statistic** \(s(c)\) (e.g. % RDS increase at T_ref residual, mV VTH shift, % Rth increase):

| Transition | Default idea (simulation knobs) |
| --- | --- |
| early | \(s > 0\) after onset |
| measurable | \(s > s_{\mathrm{meas}}\) (above healthy jitter + noise, latent) |
| advanced | \(s > s_{\mathrm{adv}}\) |
| terminal | \(s > s_{\mathrm{term}}\) or ModuleProfile-style relative RDS change, whichever config selects |

Record `cycle_early`, `cycle_measurable`, `cycle_advanced`, `cycle_terminal` (nullable if not reached by `target_cycles`) in ground truth so **detection lead time** = `cycle_detected - cycle_measurable` (or vs onset — evaluation must state which).

---

## 12. Bond-wire / interconnect degradation

### 12.1 Physical rationale (qualitative)

Power cycling repeatedly expands and contracts interconnects (wires, ribbons, clips). Fatigue can increase **conduction path resistance**. That can appear as higher RDS(on)/VDS(on) and higher conduction loss, with possible secondary heating.

This is **not** a claim that an RDS(on) increase **proves** bond-wire failure. Package, die, contact, and measurement artifacts can move RDS(on).

### 12.2 Evidence status

**Engineering evidence:** not verified in-repo. PRD/architecture list these as *potential* signatures.  

**Simulation assumption:** inject a progressive additive interconnect resistance that appears primarily on RDS(on) and VDS(on).

### 12.3 Simulated signature

Let \(d(c)\) be damage after onset.

| Quantity | Simulated relationship | Type |
| --- | --- | --- |
| Residual RDS(on) at T_ref | \(+\Delta R_{\max} \cdot d(c)\) | approximate, nearly deterministic given \(d\) |
| VDS(on) | \(\approx I_D \times R_{\mathrm{DS,on,observed}}\) when both emitted | mathematical (Ohm), plus noise |
| electrical_power (conduction part) | increases with \(I_D^2 R\) | mathematical approximation |
| Tj / Tc | modest secondary rise via extra conduction loss; **primary** temperatures still near power-cycle setpoints | weak, probabilistic via control error |
| VTH, IGSS, IDSS | **no primary injection**; tiny leakage via shared noise only | must not uniquely co-move |

**Development default:** \(\Delta R_{\max}\) on the order of 15–25% of `rds_on_ref` at full damage (configurable), so advanced modules can still sit near or across the illustrative 20% relative acceptance **without** treating that limit as a physical law.

Correlated but **non-perfect:** measurement noise, ID jitter, and temperature residuals blur the Ohm’s-law identity.

---

## 13. Die-attach / thermal-path degradation

### 13.1 Physical rationale (qualitative)

Solder or sinter die-attach and TIM/interfaces can degrade under thermal cycling, increasing thermal resistance. Junction may run hotter for the same power, or the controller may change current to hold Tj, altering the Tj–Tc relationship.

RDS(on) can rise **secondarily** because the die is hotter — that is temperature-driven, not an interconnect residual. The generator **must** apply the temperature map to the new Tj so feature residual-at-T_ref stays small unless a secondary electrical residual is explicitly configured.

### 13.2 Evidence status

**Engineering evidence:** not verified in-repo.  

**Simulation assumption:** increase latent `Rth_jc` (and optionally `Rth_ca`) with \(d(c)\). Optional small secondary RDS residual at T_ref (default **near zero**) so models that ignore temperature can be fooled — that is a **benchmark trap**, documented as such.

### 13.3 Simulated signature

| Quantity | Simulated relationship | Type |
| --- | --- | --- |
| Rth | \(R_{\mathrm{th}}(c) = R_{\mathrm{th,0}}(1 + \gamma d(c))\) | simulation assumption |
| Tj − Tc | widens for given P | follows lumped model |
| Tj | modest overshoot vs setpoint (configurable) | simulation assumption |
| Tc | may drop or shift depending on control | simulation assumption |
| RDS(on) raw | rises if Tj rises (temperature map) | temperature-driven |
| RDS(on) at T_ref | ≈ manufacturing baseline (+ optional tiny secondary) | **distinct from bond-wire** |
| VTH | follows temperature map | not a gate injection |
| IGSS / IDSS | no primary injection | — |

**Development default:** \(\gamma\) such that advanced Rth is ~20–40% above baseline (simulation knob).

---

## 14. Gate-related degradation

### 14.1 Physical rationale (qualitative)

Gate oxide and gate-related structures can shift threshold and leakages under bias and temperature. Power cycling is **not** uniquely a gate-oxide test (HTGB/HTRB are more direct). This category still exists so the first dataset can evaluate **whether detectors confuse gate signatures with package signatures**.

**Do not** claim a telemetry tuple uniquely identifies gate-oxide breakdown.

### 14.2 Evidence status

**Engineering evidence:** not verified in-repo. HTGB-like physics is not simulated in detail.

**Simulation assumption:** progressive VTH shift plus IGSS increase, with a weaker IDSS correlation.

### 14.3 Simulated signature

| Quantity | Simulated relationship | Type |
| --- | --- | --- |
| VTH | \(V_{\mathrm{TH}}(c) = V_{\mathrm{TH}}(T_j) + \sigma_{\mathrm{dir}} \cdot \Delta V_{\max} \cdot d(c)\) | simulation; `shift_sign` per module (+ or −) |
| IGSS | \(I_{\mathrm{GSS}} = I_{\mathrm{base}} + \Delta I_{G} d(c)\) (optional mild exponential in \(d\)) | simulation, noisy |
| IDSS | weaker correlated increase | probabilistic |
| RDS(on) at T_ref | small optional coupling if VTH shift moves the device toward weaker inversion at fixed VGS (default **small**) | approximate, optional |
| Rth, ΔTj | no primary injection | — |

**Non-perfect correlation:** IGSS outliers, missingness, and independent IDSS noise so a classifier cannot get 100% accuracy from one channel.

---

## 15. Cross-parameter relationships

Summary of dependence type. “Deterministic” means the **latent** equation is determined given latents; observations remain noisy.

| Relationship | Latent type | Notes |
| --- | --- | --- |
| RDS(on) ↔ Tj | approximate deterministic map | §8.2; healthy and all mechanisms |
| RDS(on) ↔ ID | measurement condition; VDS(on)≈ID·RDS | Ohm approximation |
| RDS(on) ↔ interconnect damage | approximate deterministic residual | bond-wire category |
| RDS(on) ↔ Rth damage | mainly **via Tj**, not via T_ref residual | die-attach |
| Tj ↔ P ↔ Rth | lumped approximate | §8.4 |
| Tj ↔ cooling / Tc | approximate + control targeting | setpoint-dominated |
| VTH ↔ Tj | approximate linear | simulation coefficient |
| VTH ↔ gate damage | approximate residual | gate category |
| IGSS ↔ gate damage | noisy monotonic | not 1–1 |
| IDSS ↔ gate damage | weak probabilistic | — |
| VDS, VGS, ID ↔ TestProfile | near-setpoint + jitter | not mechanism ids |
| All observed ↔ sensors | stochastic | §16 |

**Independent columns are forbidden** as a generation strategy. Independence would make multivariate detectors meaningless and investigation correlation tools vacuous.

---

## 16. Sensor and measurement model

### 16.1 Latent vs observed

```text
latent_state(c)  --sensor model-->  TelemetryRecord.measurements
```

Ground truth stores latents (or sufficient summaries). Telemetry stores observations only.

### 16.2 Configurable effects (applied in stage 7)

| Effect | Default role | Notes |
| --- | --- | --- |
| Gaussian measurement noise | always on | per-channel σ; **must not** swamp measurable-stage amplitudes |
| Sensor bias | small, per module or per channel | constant offset |
| Calibration drift | optional slow ramp | distinct from mechanism residual; labeled in ground truth if injected |
| Quantization | optional | e.g. temperature 0.1 °C; off by default |
| Sampling variation | observation at cycle + small timestamp jitter | §18 |
| Outliers / missing / duplicates | **off** unless scenario `data_quality_stress` | §17 |

**Development default noise (simulation convenience, not instrument datasheets):**

| Channel | σ (example) | Constraint |
| --- | --- | --- |
| RDS_on | 0.02 mΩ | ≪ measurable interconnect residual |
| VTH | 5 mV | ≪ gate ΔV measurable |
| IGSS | 0.02 µA | — |
| IDSS | 2 µA | — |
| Tj, Tc, Ta | 0.3 °C | — |
| VDS | 0.5 V | — |
| ID | 0.5 A | — |
| VGS | 0.05 V | — |

Invalid values: `status: invalid` with optional out-of-range number; missing: `status: missing` and **no** value (Telemetry contract). Never fill missing with 0.

Derived channels (`RDS_on`, `delta_Tj`, `electrical_power`, optional `Rth`) use `origin: derived` and a `derivation.method` string naming the **simulator method** (e.g. `synthetic_lumped_rds_temperature_map`), not a fake lab procedure.

---

## 17. Data-quality scenarios

Quality defects are **not** mixed into every dataset.

GenerationConfig `scenario` selects a preset. Rates below are **zero** unless the scenario enables them.

| Defect | Config keys | Telemetry representation |
| --- | --- | --- |
| Missing values | `p_missing` per channel | `status: missing`, omit `value` |
| Duplicates | `p_duplicate_record` | extra record, same or near timestamp/cycle |
| Timestamp irregularity | `p_time_jump`, jitter σ | gaps, non-uniform Δt |
| Invalid values | `p_invalid` | `status: invalid` (NaN/Inf still **forbidden**) |
| Sensor spikes | `p_spike`, amplitude | rare large deviation, `valid` or `invalid` per config |
| Dropout runs | `p_dropout`, run length | consecutive missing |

Scenarios:

1. **`clean_healthy`** / **`degradation_benchmark`:** quality rates = 0 (only Gaussian noise + bias).  
2. **`data_quality_stress`:** nonzero rates; still a valid Telemetry stream (no NaN/Inf).

This separates **ML benchmark cleanliness** from **validator testing**.

---

## 18. Temporal structure

### 18.1 Cycle-level first dataset

**Priority:** one observation per `observation_stride_cycles` at a consistent `cycle_phase` (development default: `heating`, representing a near-peak or specified measurement window).

Do **not** emit heating+cooling+dwell at 1 s for 100k cycles in v1 (~10^8+ rows). Within-cycle waveforms are out of scope until a later configuration explicitly requests them (e.g. 2–3 phases per cycle at coarse stride).

### 18.2 Timestamps

- Timezone-aware UTC  
- Base timestamp in GenerationConfig (`t0`)  
- Cycle \(c\) time: \(t = t_0 + c \cdot T_{\mathrm{cycle}}\) with \(T_{\mathrm{cycle}}\) from TestProfile `cycle_duration_s` (illustrative 6 s)  
- Optional jitter: small compared to \(T_{\mathrm{cycle}}\)  
- Ordering: strictly increasing `timestamp` within a module/test unless a quality scenario injects duplicates  

`cycle_number` is the integer cycle index (`>= 0`), aligned with TestProfile meaning, **monotonic non-decreasing** in the clean scenarios (strictly increasing when one row per cycle).

### 18.3 Ordering guarantees (clean scenarios)

For each `(module_id, test_id)`:

- sorted by `cycle_number` then `timestamp`  
- unique `telemetry_id`  
- no backward cycles  

### 18.4 Volume (development)

750 modules × ~501 cycles × ~10 measurements ≈ 3.8e5 records — suitable for local pytest-scale subsets and full parquet later. `n_modules` and stride remain the scaling knobs.

---

## 19. Ground truth

Mandatory. **Separate files.** Never joined into model **inputs**.

Conceptual record (schema implemented in M4-B):

| Field | Role |
| --- | --- |
| `module_id` | instance |
| `lot_id` | lot |
| `module_profile_id` | type |
| `test_id` | stress config |
| `health_state` | `healthy` \| `degrading` \| `terminal` |
| `degradation_mechanism` | one of the four categories (`healthy` if none) |
| `degradation_stage` at end of test | stage enum |
| `onset_cycle` | null if healthy |
| `cycle_early` / `cycle_measurable` / `cycle_advanced` / `cycle_terminal` | nullable |
| `degradation_severity` | final \(s\) or \(d\) |
| `rate_scale` | module rate draw |
| `terminal_cycle` | alias of cycle_terminal |
| `simulation_seed` | dataset or module subseed |
| `generator_version` | code version |
| `mechanism_model` | id of signature model (e.g. `bond_wire_v1`) |
| `generation_assumptions` | pointer or inline ids |
| `latent_baselines` | optional: rds_on_ref, vth_ref, rth_0 (evaluation/debug; still not telemetry) |

Optional per-cycle latent file is **out of default scope** (size). If added later, it stays under `ground_truth/`, never in `telemetry/`.

**Synthetic ground truth is not physical confirmation.**

---

## 20. Early detection

The dataset must support:

> How early did the system identify abnormal behavior?

Requirements:

1. `onset_cycle` and `cycle_measurable` stored  
2. Multiple observations **between** onset and advanced/terminal for typical degrading modules (`observation_stride` fine enough that measurable stage lasts many points)  
3. Healthy controls with similar temperature and stress  
4. Evaluation (later) reports lead time vs `cycle_measurable` (primary) and vs `onset_cycle` (stricter)  
5. Models that only fire at `terminal` fail the early-detection objective even if ROC looks fine on last-cycle labels  

**Simulation assumption:** `s_meas` is set using latent residuals **before** noise so “measurable” means **detectable in principle**, not “detectable by a specific algorithm after noise.”

---

## 21. Class balance

Do **not** force equal class counts as if they were natural.

`population_mix` is a GenerationConfig map, e.g. for `degradation_benchmark` **development default (simulation choice, not prevalence):**

| Category | Fraction |
| --- | --- |
| healthy | 0.70 |
| bond_wire_interconnect | 0.10 |
| die_attach_thermal_path | 0.10 |
| gate_related | 0.10 |

`clean_healthy`: 1.00 healthy.  
`data_quality_stress`: typically reuses the degradation mix plus quality defects.

Assignment: multinomial by module (or stratified by lot so each lot contains all classes — **configurable**; default **stratify by lot** so lot holdout still sees every class).

---

## 22. Train / validation / test considerations (do not implement splits in M4)

**Do not** randomly split telemetry **rows**.

A module’s early cycles in train and later cycles in test leak the same manufacturing offsets, sensors, and degradation path unless the task is explicitly **forecasting**.

| Split family | Unit | Use |
| --- | --- | --- |
| Module-level | whole `module_id` | default unsupervised/supervised module scoring |
| Lot-level | whole `lot_id` | generalization to a new manufacturing batch |
| Temporal holdout | time/cycle cutoff **within** declared forecast task | future-state prediction only |

Unsupervised anomaly training should use **healthy (or unlabeled) modules** only; mechanism labels remain evaluation-only.

Specification implication for the generator: ids and lots must be stable and recorded so a later evaluation pipeline can split without peeking at labels in the telemetry files.

---

## 23. Reproducibility

Deterministic given:

- `generation_config` (canonical JSON)  
- `random_seed`  
- `generator_version`  
- ModuleProfile content hash or explicit `module_profile_version`  
- TestProfile content hash or explicit `test_profile_version`  

Two runs with the same inputs must produce byte-stable parquet **or** documented float tolerance if libraries differ — M4-B should prefer a single RNGstream (e.g. `numpy.random.Generator`) with documented spawn policy: dataset seed → lot seeds → module seeds → measurement streams, so adding a module at the end does not reshuffle earlier modules (**simulation/engineering requirement**).

---

## 24. Provenance

Dataset-level (`metadata/dataset.json` + `provenance/provenance.json`):

| Field | Required |
| --- | --- |
| `dataset_id` | yes |
| `data_origin` | yes, `synthetic` |
| `generator_version` | yes |
| `generation_timestamp` | yes, UTC |
| `random_seed` | yes |
| `module_profile_id` / `module_profile_version` / hash | yes |
| `test_profile_id` / `test_profile_version` / hash | yes |
| `schema_version_module_profile` | yes (`1.0.0`) |
| `schema_version_test_profile` | yes |
| `schema_version_telemetry` | yes |
| `generation_config` | yes (file or inline) |
| `assumptions` | yes (`assumptions.json`) |
| `mechanism_models` | yes |
| `source_references` | yes (may be empty list if none verified) |
| `scenario` | yes |

Telemetry-level provenance repeats `data_origin: synthetic` and `source_dataset: <dataset_id>`.

---

## 25. Source and evidence policy

| Class | Rule |
| --- | --- |
| **A. Verified external engineering information** | Cite only after a real source is in the knowledge base. **None in M4-A.** |
| **B. Simulation assumptions** | Allowed if labeled; required for mix, σ, onset, ΔR_max, γ, α_VTH, etc. |
| **C. Mathematical convenience** | Linear T maps, power-law \(d(c)\), additive Gaussian noise |
| **D. Synthetic ground truth** | Injected labels; not lab FA |

For every important degradation relationship, **external evidence is required before treating it as diagnostic knowledge** in the product. Implementation of M4-B may proceed on **labeled simulation assumptions** so software can be built; reports and agents must not describe those signatures as experimentally validated.

Do not invent citations. PRD mentions AQG 324 as a *potential* standard family; it is **not** used as a verified source here.

---

## 26. Dataset output structure

Architecture and `tech-stack.md` place datasets and generators under repository-root **`ml/`**, not a new top-level `datasets/` tree. Conceptual layout for M4-B:

```text
ml/
├── generators/                 # M4-B code (not created in M4-A)
└── datasets/
    └── synthetic/
        └── <dataset_id>/
            ├── metadata/
            │   ├── dataset.json
            │   ├── generation-config.json
            │   └── assumptions.json
            ├── telemetry/
            │   └── telemetry.parquet
            ├── ground_truth/
            │   └── ground-truth.parquet
            └── provenance/
                └── provenance.json
```

Optional later: `telemetry/` sharded by lot; `README` stating synthetic origin in the first line.

This directory is **not** created in M4-A.

---

## 27. Dataset scenarios

Each scenario is an independent GenerationConfig (+ seed) and must be reproducible alone.

### 27.1 `clean_healthy`

Mostly or entirely healthy modules; manufacturing + temperature + stress jitter + measurement noise; **no** quality defects; ground truth mechanism `healthy`.

**Purpose:** data-quality engine true-negative paths; unsupervised “normal” training corpus.

### 27.2 `degradation_benchmark`

Healthy + three degradation categories; hidden ground truth; clean measurements.

**Purpose:** anomaly/degradation/investigation/lead-time evaluation.

### 27.3 `data_quality_stress`

Same population intent as 27.2 (or config-equal mix) **plus** controlled missingness, outliers, duplicates, timestamp issues.

**Purpose:** validator PASS/WARNING/BLOCKED behavior; robustness tests. **Not** the primary ML leaderboard unless explicitly declared.

---

## 28. Acceptance criteria (for the future generator)

Deterministic checks M4-B must pass (not implemented now):

1. Every telemetry row validates as `TelemetryRecord` (Pydantic + JSON Schema as applicable).  
2. Every `module_id` in telemetry appears in ground truth and vice versa.  
3. Every `test_id` matches the bound TestProfile; TestProfile `module_profile_id` matches the bound ModuleProfile.  
4. Every `lot_id` is non-empty and consistent between telemetry and ground truth.  
5. Timestamps are timezone-aware UTC.  
6. In clean scenarios, `cycle_number` is monotonic per module/test.  
7. `provenance.data_origin` is `synthetic` on every record.  
8. No forbidden analytical/ground-truth fields on telemetry.  
9. No NaN/Inf in any numeric measurement `value` or `uncertainty`.  
10. Missing samples have no numeric value.  
11. Population counts match config (`n_modules`, lot sizes, mix within rounding).  
12. Healthy modules have `onset_cycle` null and mechanism `healthy`.  
13. Degrading modules: residual is ~0 before onset; non-decreasing damage after onset (within documented jitter).  
14. Bond-wire modules show larger T_ref RDS residual than die-attach at comparable Tj **in the latent summaries** (test the design intent).  
15. Generator config, seed, versions, and assumption ids are recorded.  
16. Parquet/JSON artifacts live only under the dataset_id directory.  
17. `dataset_id` on telemetry matches metadata.  

Do not weaken ModuleProfile/TestProfile/Telemetry tests to make generation easier.

---

## 29. Documentation map

This file is the M4-A deliverable. Section map:

| # | Content |
| --- | --- |
| 1 | Purpose |
| 2 | Scope |
| 3 | Philosophy |
| 4 | Input contracts |
| 5 | Population generation |
| 6 | Manufacturing variation |
| 7 | Healthy behavior |
| 8 | Temperature effects |
| 9 | Stress effects |
| 10–14 | Mechanisms and progression |
| 15 | Cross-parameter relationships |
| 16–17 | Sensor model and data quality |
| 18 | Temporal structure |
| 19–21 | Ground truth, early detection, class mix |
| 22–24 | Splits, reproducibility, provenance |
| 25 | Evidence policy |
| 26–27 | Output layout and scenarios |
| 28 | Acceptance criteria |
| 30 | GenerationConfig |
| 31–32 | Limitations and evidence backlog |

---

## 30. Generation configuration (conceptual)

M4-B should persist this as `generation-config.json`. Fields:

```text
dataset_id
scenario                  # clean_healthy | degradation_benchmark | data_quality_stress
generator_version
random_seed

module_profile_id
module_profile_version    # or content hash
test_profile_id
test_profile_version

n_modules
n_lots
modules_per_lot           # or explicit lot sizes
population_mix            # fractions of the four categories
stratify_mix_by_lot       # bool

observation_stride_cycles
cycle_phase               # heating | cooling | dwell
t0                        # UTC start
include_channels          # TelemetryParameter list

manufacturing_variation   # sigmas, truncation
stress_variation          # ID / ΔTj / VDS sigmas
healthy_temporal_jitter

temperature_model         # T_ref, interpolation mode, alpha_vth
thermal_model             # lumped flags, P_sw treatment, control tracking error

degradation:
  onset_distribution      # family + parameters
  progression_exponent_p
  rate_scale_lognormal
  stage_thresholds
  bond_wire: { delta_rds_max_rel, ... }
  die_attach: { gamma_rth, secondary_rds_ref, tj_overshoot }
  gate: { delta_vth_max, igss_delta, idss_coupling, shift_sign_policy }

sensor:
  gaussian_sigma          # per channel
  bias
  calibration_drift
  quantization

quality:                  # ignored unless data_quality_stress
  p_missing
  p_duplicate_record
  p_invalid
  p_spike
  p_dropout
  timestamp_jitter

notes                     # free text: synthetic development dataset
```

Do not implement the Pydantic model in M4-A unless a later task requires it.

---

## 31. Known limitations

1. Not a validated electro-thermal or reliability-physics model.  
2. Single primary mechanism per module in v1.  
3. No FEM, no bond-wire count, no current crowding map.  
4. Switching loss is a stub.  
5. Power-cycle lifetime is **assigned**, not predicted from ΔTj.  
6. Illustrative ModuleProfile/TestProfile numbers are placeholders.  
7. Cycle-level only; no switching-cycle EMI or gate-charge waveforms.  
8. Half-bridge is treated as one telemetry stream per module (not per switch) unless config later splits channels.  
9. Linear RDS(T) and VTH(T) are convenience maps.  
10. Measurement σ is not from a calibrated DAQ.  
11. Class mix is not field prevalence.  
12. Cannot support claims about real product qualification.

---

## 32. Assumptions requiring external evidence (before product diagnostic use)

Implementation of a **labeled simulator** may proceed without these. **Investigation language and reliability conclusions** must not treat them as confirmed until evidence is ingested.

1. Quantitative RDS(on) vs Tj for the target SiC MOSFET family  
2. Quantitative VTH vs Tj  
3. Bond-wire fatigue ↔ RDS(on) / VDS(on) magnitudes under the stated VDS/ID/ΔTj  
4. Die-attach voiding/solder fatigue ↔ Rth and Tj–Tc signatures for this package  
5. Gate-related drift under **power cycling** (vs HTGB/HTRB) — whether v1 gate category is even a realistic PC signature  
6. Manufacturing lot/module σ  
7. Sensor accuracies  
8. Any lifetime model (Coffin–Manson, LESIT, Bayerer) parameters  
9. Prevalence of mechanisms  
10. Mapping of ModuleProfile acceptance (e.g. 20% RDS) to “failure” in a given standard  

Until then, agents must use statuses such as **Insufficient Evidence** / **Ambiguous** / **Anomaly Detected — Mechanism Unresolved** rather than confirmed physical failure.

---

## 33. Implementation boundary (M4-A)

This milestone **does not** create `dataset_generator.py`, mechanism Python modules, parquet/CSV datasets, or generator unit tests.

M4-B implements the generator under `ml/generators/`, writes datasets under `ml/datasets/synthetic/`, and adds tests for the acceptance list in §28 without changing M1–M3 contracts unless a true blocking gap appears during implementation.
