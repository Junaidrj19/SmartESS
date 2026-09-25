# M9 Corpus Coverage and Gap Analysis

Generated: 2026-09-24
Corpus version: `1.0.0`
Manifest: `knowledge_base/metadata/corpus.json`
ChromaDB collection: `evidence` (360 chunks, 19 documents)
Embedding model: `sentence-transformers/all-MiniLM-L6-v2`

This report is generated from the manifest and from the inspected PDFs. Coverage is
declared only where the extracted text of a document actually discusses the item.
Gaps below are real gaps, not approximations.

---

## 1. Corpus status

| Status | Count |
| --- | --- |
| Candidates in manifest | 37 |
| `VERIFIED` (production corpus) | 19 |
| `NEEDS_MANUAL_ACCESS` | 13 |
| `OCR_REQUIRED` | 1 |
| `REJECTED` | 1 |
| `UNVERIFIED` (identity unresolved) | 3 |

Total PDFs downloaded and inspected: 21. Of those, 19 are usable text-extractable
documents, 1 is image-only, and 1 was rejected for an unusable text layer. Two
downloaded-but-unusable files are excluded from retrieval.

Normalised filename collisions across providers: none. No duplicate content was
detected: `--validate` reports zero `duplicate_content` errors, so no two corpus
files share a SHA-256. The corpus contains one canonical full-text version per
intellectual work; no work is represented twice.

---

## 2. Source-type coverage (production corpus)

| Source type | Count | Target from the brief | Verdict |
| --- | --- | --- | --- |
| `standard` | 1 | 3–5 | **Below target** |
| `manufacturer` | 12 | 8–12 | Met |
| `peer_reviewed` | 4 | 6–10 | **Below target** |
| `review` | 2 | 3–5 | **Below target** |

The standards, peer-reviewed and review buckets all fall short for the same root
cause: the specific candidate documents are paywalled or publisher-blocked, not
absent. See section 7.

## 3. Mechanism coverage (production corpus, EXPLICIT)

| Mechanism | Documents |
| --- | --- |
| `bond_wire_interconnect` | 8 |
| `die_attach_thermal_path` | 8 |
| `gate_related` | 15 |
| `thermal_path` | 6 |
| `package_interconnect` | 9 |
| `cross_cutting` | 11 |

`gate_related` is the best-covered mechanism, largely on the strength of gate-oxide
and threshold-voltage material in the Wolfspeed and Infineon notes plus three
open-access gate-oxide papers. `thermal_path` is the thinnest: only six documents
discuss thermal resistance / junction temperature as a studied quantity, and much of
that is thermal resistance as a *measurement* rather than as a *degradation path*.

## 4. Observable coverage (production corpus, EXPLICIT)

| Observable | Documents |
| --- | --- |
| `VTH` | 14 |
| `RDS_on` | 11 |
| `Tj` | 11 |
| `thermal_resistance` | 8 |
| `IGSS` | 7 |
| `electrical_power` | 7 |
| `IDSS` | 6 |
| `Tc` | 4 |
| `VDS_on` | 3 |

`VDS_on` is the thinnest observable. It is covered mainly by ECPE AQG 324 (module
test on-state voltage) and the Energies forward-power-cycling paper; most other
sources report `RDS_on` instead, which is a different electrical quantity.

## 5. Test-condition coverage (production corpus, EXPLICIT)

| Test condition | Documents |
| --- | --- |
| `power_cycling` | 8 |
| `thermal_cycling` | 8 |
| `gate_bias` | 7 |
| `HTRB` | 5 |
| `HTGB` | 3 |
| `HTOL` | 1 |

`HTOL` is covered by exactly one document (the NIST gate-oxide status paper), and
that coverage is incidental rather than a dedicated operating-life treatment.
`HTGB` at three documents is adequate but not deep. **No document in the corpus
reports an HTOL test programme of its own.** The candidate that would have filled
this — JESD22-A108 *Temperature, Bias, and Operating Life* — is paywalled.

## 6. Manufacturer / organisation coverage

| Organisation | Documents (production) |
| --- | --- |
| Wolfspeed | 7 |
| Infineon Technologies | 4 |
| MDPI (peer-reviewed/review) | 3 |
| ECPE | 1 |
| ROHM Semiconductor | 1 |
| Microchip Technology | 1 |
| Toshiba Electronic Devices & Storage | 1 |
| Michigan State University (arXiv) | 1 |
| University of Sheffield / White Rose | 1 |
| NIST | 1 |

Six device manufacturers are represented (Wolfspeed, Infineon, ROHM, Microchip,
Toshiba, plus ECPE as the industry standards body). onsemi and STMicroelectronics
were both searched; their relevant reliability documents are served from hosts that
reject automated retrieval, and no legitimate publicly downloadable equivalent was
found, so neither is represented.

---

## 7. Evidence gaps

### 7.1 Standards (largest gap)
Only **one** standard was obtained: ECPE AQG 324, Release 04.1/2025, which is
published as a public document by ECPE. The other four candidates could not be
legitimately obtained:

| Candidate | Why not obtained |
| --- | --- |
| AEC-Q101 | `aecouncil.com` rejects the client TLS handshake from this environment; document not retrieved. AEC publishes its documents publicly, so this is a retrieval-environment limitation, not a paywall. |
| JEP194 | JEDEC licence-accepting download; `jedec.org` returns HTTP 403 to automated clients. |
| JEP183A | Same. Title/revision confirmed from JEDEC's own page; PDF not retrieved. |
| JESD22-A108 | Same; the intended letter revision is also ambiguous. |

Consequence: the corpus has **no AEC qualification-test coverage at all**, and
**no first-party JEDEC measurement-procedure coverage**. The AQG 324 SiC annex
partially compensates for qualification-test structure, but it is one document.

### 7.2 VTH hysteresis and measurement-condition effects
`VTH` is the most-covered observable, but **no corpus document measures threshold-
voltage hysteresis** under differing sweep conditions. The document written for
exactly this (JEP183A) is paywalled. Any statement about hysteresis effects in SmartESS
currently has no grounding in this corpus.

### 7.3 HTOL
See section 5. One incidental mention. The dedicated candidate (JESD22-A108) is
paywalled.

### 7.4 Primary research on power cycling of discrete devices
Only one primary research paper on power cycling was obtainable (Energies 17(11):2557).
Candidates P1, P2, P4, P6 and P8 — which are precisely the power-cycling, online
ageing-detection and TO-package power-cycling papers — are all closed access with no
open-access copy located.

### 7.5 Temperature-compensated RDS(on) monitoring
The retrieval query *"temperature compensated RDS(on) degradation monitoring"* returned
the **weakest** matches of the seven retrieval tests (best distance ≈ 1.05, versus
0.50–0.60 for the well-covered queries). No document in the corpus describes a
temperature-compensation method for RDS(on)-based monitoring. The corpus establishes
that RDS(on) depends on gate voltage and temperature (Wolfspeed PRD-08937,
Infineon AN2018-09) — which is the reason compensation is necessary — but does not
itself provide the compensation methodology.

### 7.6 HTRB / HTGB depth
Present but shallow, and concentrated in ECPE AQG 324 and the Wolfspeed
reliability whitepaper. No corpus document reports a dedicated HTRB or HTGB
degradation study with measured parameter trajectories.

---

## 8. Redundant documents

No exact duplicates (identical SHA-256) exist. However there is **thematic overlap**
that should be understood when weighting evidence:

- `wbg-packaging-reliability-review` (Energies 2022) and `prognosis-power-sic-mosfets`
  (Entropy 2026) both survey package and gate degradation broadly, and both compete
  for the same retrieval results.
- `wolfspeed-designed-to-last` and `wolfspeed-enhancing-system-durability-packaging`
  are both November 2025 Wolfspeed whitepapers sharing a framing and some figures.
- `wolfspeed-power-cycling-lifetime` and `wolfspeed-package-induced-failures` both
  cover package-level failure candidates.
- `precursors-gate-oxide-degradation-sic-mosfets` (arXiv 2018) and
  `gate-oxide-effect-sic-mosfet-whiterose` (ECCE 2022) are independent gate-oxide
  studies that measure overlapping quantities (`VTH`, `IGSS`).

This overlap is not duplication of an intellectual work, but it does mean the
corpus is **less independent than its document count suggests**, especially for
gate-oxide claims.

## 9. Potential contradictions to watch

These are genuine tensions in the literature present in the corpus — they are
findings, not defects, and they argue against deterministic diagnostic rules:

1. **Whether `VTH` shift is a usable early precursor.** The arXiv precursor study
   presents `VTH`, gate plateau voltage and gate plateau time as usable degradation
   precursors; the NIST status paper argues that extrapolating gate-oxide lifetime
   from simple screening is unreliable, and the Entropy review concludes that
   indicator-to-mechanism mappings are generally ambiguous and require multi-parameter
   models.
2. **Whether `RDS_on` increase indicates package degradation.** The Energies forward
   power-cycling paper and the Wolfspeed package notes associate `RDS_on` movement
   with bond-wire and die-attach degradation, while Wolfspeed PRD-08937 shows `RDS_on`
   also changing strongly with gate voltage and temperature, and the Toshiba review
   associates it with bipolar degradation of the body diode. Three different
   candidate causes for the same observable.
3. **Whether `IGSS` increase implies gate-oxide breakdown.** The corpus treats gate
   leakage as a *precursor* (arXiv, White Rose) while also documenting gate-oxide
   *breakdown* reliability separately (NIST). Precursor and catastrophic failure are
   not the same event.
4. **`Tj` / `Tc` interpretation.** AQG 324 defines `Tj`/`Tc` and thermal resistance as
   measured test parameters, whereas the Wolfspeed power-cycling whitepaper uses them
   as degradation inputs. The same quantity plays a measurement role and an inference
   role, which is a direct argument against reading a thermal rise as a mechanism.

## 10. Missing diagnostic measurements

- No document measures **threshold-voltage hysteresis** by sweep direction/rate.
- No document provides a **temperature-compensated `RDS_on`** measurement method.
- No document reports **`Tc`** as a primary monitored quantity (only 4 documents
  mention it at all, and usually in passing).
- No document in the corpus reports a **`VDS_on`** trajectory during a degradation
  test except the Energies forward power-cycling paper.
- No document performs **time-resolved gate-leakage spectroscopy**, so `IGSS` is
  available only as a scalar trend.

---

## 11. Targeted check against the SmartESS gap list

| # | Area | Supported by the corpus? | Notes |
| --- | --- | --- | --- |
| 1 | Bond-wire / interconnect degradation | **Yes, explicit** | 8 documents; strongest in Wolfspeed PRD-09129, the Energies power-cycling paper and both reviews. |
| 2 | Die-attach degradation | **Yes, explicit** | 8 documents, including a dedicated die-attach/sintering note (Wolfspeed PRD-07969). |
| 3 | Gate-oxide degradation | **Yes, explicit** | 15 documents — the best-covered area, but see section 8 on source independence. |
| 4 | Thermal-path degradation | **Partial** | 6 documents, and mostly thermal resistance as a measurement rather than a degradation path. |
| 5 | Package / interconnect degradation | **Yes, explicit** | 9 documents; Wolfspeed PRD-09129 is the systematic reference. |
| 6 | `RDS_on` temperature dependence | **Yes, explicit** | Wolfspeed PRD-08937 (25 °C vs 175 °C), Infineon AN2018-09, Microchip AN6239. |
| 7 | `VTH` hysteresis / measurement effects | **No** | Not covered by any corpus document. JEP183A is the missing source. |
| 8 | `IGSS` as a degradation precursor | **Yes, explicit** | arXiv precursor study, White Rose gate-oxide paper, Entropy review, AQG 324 (as a measured parameter). |
| 9 | `Tj` / `Tc` interpretation | **Partial** | `Tj` is well represented (11 documents) but is used both as a measured parameter and as an inferential input; `Tc` is thin (4). |
| 10 | Thermal resistance | **Yes, explicit** | 8 documents; AQG 324 defines the measurement, Wolfspeed defines the process/construction. |
| 11 | Power-cycling failure mechanisms | **Yes, explicit** | 8 documents, including a full test programme in AQG 324 and a primary study in Energies. |
| 12 | Gate-bias stress | **Yes, explicit** | 7 documents; AQG 324 defines HTGB and dynamic gate stress. |
| 13 | HTOL | **Barely** | 1 incidental mention (NIST). JESD22-A108 missing. |
| 14 | HTRB | **Yes, explicit** | 5 documents, concentrated in AQG 324 and the Wolfspeed reliability whitepaper. |
| 15 | HTGB | **Yes, explicit** | 3 documents (AQG 324, ROHM app note, Wolfspeed reliability whitepaper). Shallow. |

**Not supported:** threshold-voltage hysteresis and measurement-condition effects (#7);
high-temperature operating life as a studied test (#13).
**Weakly supported:** thermal-path degradation (#4), `Tj`/`Tc` interpretation (#9),
HTGB depth (#15).

## 12. What would close the gaps, in priority order

1. Obtain **JEP183A** — the single highest-value missing document; it is the direct
   source for `VTH` measurement and hysteresis behaviour (gap #7).
2. Obtain **ECPE AQG 324 companion material** and **AEC-Q101** to give the corpus
   automotive-qualification coverage.
3. Obtain **JEP194** and **JESD22-A108** for gate-oxide evaluation procedure and
   operating-life methodology.
4. Obtain at least one of candidates **P1, P2, P4, P8** for primary power-cycling
   evidence on discrete/TO-packaged devices.
5. Add an open-access **temperature-compensated `RDS_on` monitoring** source.
