# 🏔️ Step 5a — Terrain: Elevation, Slope, Aspect

<!-- AUDIT-UPDATE-2026-09-25 -->
> ### Audit update (2026-09-25)
> This repository's step was recalculated independently from the raw data in a full end-to-end audit.
> **Corrected results, reproduction checks and audit code: [`AUDIT_2026-09-25.md`](AUDIT_2026-09-25.md)** and `audit_2026-09-25/`.
> Earlier text below is kept for the record (it also remains in the git history). Statements superseded by the audit:
>
> - **−46.9 m elevation**: located at the Neyveli open-cast lignite mines; most likely real terrain, not an SRTM artefact.
>
> **Pipeline rerun (2026-09-25).** The notebook was corrected and re-executed end-to-end, and the result tables below now come from that rerun:
> - Fire points are rasterised to their *containing* pixel (`floor`, not `round`, which displaced 74.9% of points by one pixel).
> - Statistics use the final India mask (4,160,963 valid DEM pixels within Step 6's 4,161,009-pixel India grid).
>
> The previous values used an earlier, wider mask (4,173,743 pixels); they are in the git history. The rerun elevation mean (736.53 m) matches the independent audit recalculation (`audit_2026-09-25/results/R6_report.json`, r = 0.9999999993).
<!-- AUDIT-UPDATE-2026-09-25 -->


**Notebook:** [`Step5a_Terrain_Elevation_Slope_Aspect.ipynb`](Step5a_Terrain_Elevation_Slope_Aspect.ipynb)
**Kernel:** `firerisk-anaconda3` (Python 3.12.7, base `C:\Users\Admin\anaconda3\python.exe`)

> **Added 2026-08-18, numbered 2026-08-19, split into its own repo 2026-08-19.** Runs
> alongside Step 4 (FLDAS), feeds Step 6 (Integration). Was originally paired with the
> distance-to-roads/railways/waterways work in one `Terrain_Accessibility_Analysis/`
> folder/repo — split into two independent repos per user request, but both notebooks
> stay numbered Step 5a / Step 5b (sibling repo: `Distance_Roads_Railways_Waterways_
> Analysis/`, Step 5b). No further renumbering — Integration stays Step 6, Model stays
> Step 7, PINN stays Step 8. See root `CLAUDE.md` for the full eight-step pipeline.

## Why this step exists

Direct extraction from the user's own copy of Biswas, Mahato & Joshi (2025) — the
project's reference paper — showed its actual MaxEnt model uses **15 predictor
variables** (its Table 3), not the 11 this project's docs had been claiming before a
2026-08-18 correction pass (see the Integration repo's `METHODOLOGY.md` for that fix).
This notebook builds 3 of the 6 variables this pipeline had zero coverage of: the
topographic/biophysical factors — **slope** (5.6% variable importance / **16.7% model
contribution** — their *second-highest* contribution variable after NDVI), **aspect**
(1.7% / 3.8%), and **elevation** (2.4% / 2.0%). Combined, these three account for
**9.7% of their model's total importance and 22.5% of its total contribution**
(**corrected 2026-09-23** — an earlier version of this sentence mislabeled the
importance sum as a contribution sum; the true combined contribution is
substantially higher because slope's own 16.7% contribution dominates the group).
The other 3 missing variables (distance
to roads/railways/waterways) are the sibling repo's Step 5b. Together, Step 5a + 5b
close all 6 of the pipeline's remaining gaps, bringing the full pipeline (Steps 1–4 plus
this pair) to **15/15 predictor-group parity** with Biswas et al.'s Table 3 — wired
into Step 6's integrated stack on 2026-08-20.

## Why this step, and how (plain-language walkthrough)

Terrain shapes fire behavior through three distinct, well-established mechanisms: fires
spread faster moving **upslope** because radiant and convective heat preheats and dries
uphill fuel ahead of the flame front before it arrives (Rothermel 1972 — the standard
wildfire-spread-model justification for slope's outsized effect); **aspect** controls
solar exposure, so south/southwest-facing slopes in the northern hemisphere receive more
direct insolation, run drier, and carry more flammable fuel than north-facing slopes;
and **elevation** is a proxy for temperature and vegetation-zone gradients that jointly
shape fuel type and moisture. These three variables were the last topographic gap in
this pipeline — everything else (NDVI, LST, FLDAS climatic variables, land cover) was
already built by Steps 2–4, but terrain itself had zero coverage until this step was
added 2026-08-18/19/20. The output here (six GeoTIFFs: elevation, slope, aspect ×
native-1km and 0.25°-comparison) is consumed by Step 6, which stacks it alongside every
other step's rasters into the single `Integrated_FireRisk_Stack.tif` /
`Integrated_FireRisk_Pixels.parquet` that Step 7's Random Forest/MaxEnt models and
Step 8's CDR-PINN both train on directly.

## Method

**Input:** SRTMGL3 (90m) DEM, mosaicked from four OpenTopography latitude-band requests
(6.5–14.25°N, 14.25–22.0°N, 22.0–29.75°N, 29.75–37.5°N — a single full-India request
exceeded even the 90m product's 4,050,000 km² area cap).
**Method:** Horn's-method gradient computed at native 90m resolution *before* resampling
to the shared NDVI grid (computing slope/aspect after downsampling would smooth away the
terrain detail that makes them useful predictors), GPU-vectorized with a fallback to
NumPy, latitude-corrected pixel spacing (longitude spacing shrinks 20.2% from India's
south to north — a flat degree→km conversion would bias every gradient).

## Results (India-masked)

| Variable | Resolution | Min | Max | Mean | P95 |
|---|---|---:|---:|---:|---:|
| Elevation (m) | native ~1km | −46.9 | 8,068.9 | 736.5 | 4,400.7 |
| Elevation (m) | 0.25° comparison | −0.2 | 6,163.2 | 771.2 | — |
| Slope (°) | native ~1km | 0.00 | 69.63 | 5.72 | 28.65 |
| Slope (°) | 0.25° comparison | 0.00 | 38.36 | 5.95 | — |
| Aspect | native ~1km | — | — | 161.1° (S), circular mean | — |

**The −46.9m elevation minimum is a known, disclosed artifact, not a data error** — the
notebook's own physical-plausibility check flagged it. It's a tail effect only (p5 is
already +25.9m). The audit located it at the Neyveli open-cast lignite mines, so it is most likely real terrain, not an SRTM artifact.
Not yet masked out — worth a one-line footnote in the paper, or a targeted patch if it
matters for a specific downstream use.

## Fire coincidence (all 541,545 Step 1 fire points; rerun 2026-09-25)

- **Slope** — fires sit at **12.35° mean vs. 5.72° nationally** (+116%). Directly
  corroborates Biswas et al.'s own finding that slope is their *second*-most-important
  variable (16.7% model contribution, behind only NDVI). 15–20° slopes are 4.8×
  overrepresented among fires; flat terrain (0–5°) is strongly underrepresented (0.33×).
- **Elevation** — non-monotonic: mid-forest bands (500–2000m) are 2.0–5.2× overrepresented,
  while both low-lying agricultural land (<200m, 0.40×) and high alpine terrain (>3000m,
  0.032×) are strongly underrepresented. Fire-point mean elevation is 637.1 m vs. 736.5 m nationally (−13.5%).
- **Aspect** — flat terrain is almost absent from fire points (0.06× enrichment),
  consistent with the slope finding. Fire-point circular mean aspect is 249° (west-southwest)
  vs. 161° nationally, and W/SW/NW are the most enriched sloped classes (2.11×, 1.77×, 1.83×).
  This is plausible given the afternoon insolation and fuel dryness of west-facing slopes. The
  pre-rerun value of 203° came from the `round` rasterisation, which shifted most points by one pixel.

## Comparison against Biswas et al. (2025)

This project computes slope and aspect from a **90m-native SRTMGL3 DEM** using a
GPU-vectorized implementation of **Horn's (1981)** 3×3-kernel gradient method — the same
algorithm ArcGIS/QGIS/GDAL's `gdaldem` and `richdem` use internally — computed *before*
resampling to the shared ~1km grid, so the terrain detail a downsampled DEM would smooth
away is preserved. Biswas et al.'s Table 2 names neither a DEM source/resolution nor a
gradient algorithm, so their slope/aspect were evidently rasterized directly at their
0.25° MaxEnt working resolution from an unspecified terrain product — a real
methodological gap in the reference paper this project's own disclosure makes explicit
rather than silently assuming a match.

This step also runs an **independent empirical cross-check** Biswas et al. do not
perform: real Step 1 fire points sit at a mean slope of 12.35° vs. 5.72° nationally — a
**+116%** enrichment. That result is not a novel claim on its own; it is a direct,
field-measurement corroboration of the same physical mechanism (upslope fire-spread
acceleration via fuel preheating, Rothermel 1972) that independently explains *why*
Biswas et al.'s own MaxEnt model ranks slope as its second-highest contribution
variable (16.7%, behind only NDVI) despite a comparatively modest 5.6% importance score.
Two independent studies — different DEM source, different gradient algorithm, different
statistical framework (MaxEnt contribution vs. this project's fire-point enrichment
ratio) — converging on the same physical driver is a stronger claim for a Q1 submission
than either result alone.

| Variable | Their importance | Their contribution | Status |
|---|---:|---:|---|
| Slope | 5.6% | 16.7% | Built · verified |
| Elevation | 2.4% | 2.0% | Built · verified |
| Aspect | 1.7% | 3.8% | Built · verified |

## Infrastructure notes worth knowing before extending this step

- One of two full notebook executions failed before a clean run: a GPU conflict with a
  concurrently-running job (this project's documented `cudaErrorAlreadyMapped`
  fragility — never run two GPU-heavy kernels against the same GPU at once; this
  specifically happened when this notebook overlapped with the sibling Step 5b
  accessibility notebook). Resolved; the notebook now runs cleanly in under 2 minutes.
- `nodata=0` ambiguity in the SRTMGL3 output (used for both open ocean and void pixels)
  is handled with a 15km coastal-proximity buffer to distinguish genuine low-lying
  coastal land from void artifacts — see the notebook's own Step 6 markdown for the
  full reasoning.

## Outputs

```
Terrain_Outputs/
├── India_SRTMGL3_DEM_mosaic.tif                                (not tracked, ~1.3GB)
├── T1_Elevation_native_1km.tif / _comparison_025deg.tif        (not tracked)
├── T2_Slope_native_1km.tif / _comparison_025deg.tif            (not tracked)
├── T3_Aspect_native_1km.tif / _comparison_025deg.tif           (not tracked)
├── T3b_Aspect_8class_native_1km.tif / _comparison_025deg.tif   (not tracked, bonus categorical aspect)
├── Terrain_summary_statistics.csv / Terrain_aspect_summary.csv (tracked)
├── Terrain_Fire_Coincidence.csv (tracked)
└── Terrain_Spatial_Maps.png / Terrain_Fire_Coincidence.png (tracked)
```

Raw source data (SRTMGL3 DEM mosaic) is a `.tif` and excluded from git per
`.gitignore`; regenerate via OpenTopography's `globaldem` API — see the notebook's
Step 0/1 for the exact latitude-banded request pattern that stays under the area cap.

## How to run

```bash
pip install -r requirements.txt
jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=firerisk-anaconda3 --ExecutePreprocessor.timeout=3600 "Step5a_Terrain_Elevation_Slope_Aspect.ipynb"
```

Requires the SRTMGL3 DEM mosaic (`Terrain_Outputs/India_SRTMGL3_DEM_mosaic.tif`) and
Step 1's fire-point archive and Step 2's NDVI grid reference file (read from their
existing locations in the wider project, never copied into this repo).

## Related work

- **Sibling repo** (Step 5b, same numbering, split off 2026-08-19): distance to
  roads/railways/waterways — `Distance_Roads_Railways_Waterways_Analysis/`.
- The burned-area vs. fire-count validation analysis lives in the Step 1 repo — see
  `Forest fire Extraction in INDIA(2000-2022)/Forest_Fire_Outputs/
  Annual_BurnedArea_vs_FireCount.csv`.

## Citation

- Biswas, U., Mahato, S., & Joshi, P.K. (2025). Spatial prediction of forest fires
  in India: a machine learning approach for improved risk assessment and early
  warning systems. *Environmental Science and Pollution Research*, 32(8), 4856–4878.
  DOI: 10.1007/s11356-025-35982-8.
- Horn, B.K.P. (1981). Hill shading and the reflectance map. *Proceedings of the
  IEEE*, 69(1), 14–47. DOI: 10.1109/PROC.1981.11918. — the gradient method this
  step's slope/aspect computation is based on.
- Rothermel, R.C. (1972). *A mathematical model for predicting fire spread in
  wildland fuels.* USDA Forest Service Research Paper INT-115. — the physical basis
  cited for slope-driven upslope fire-spread acceleration via fuel preheating.

## License

No license has been chosen yet for this repository's code.
