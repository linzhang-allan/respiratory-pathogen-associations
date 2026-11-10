# Prevalence-adjusted and temporally ordered associations among respiratory pathogens in a multicentre hospital surveillance network in China

**Code, aggregate data, and figure-reproduction resources for a retrospective observational study of respiratory pathogen co-detection and sequential detection.**

This repository accompanies the study:

> **Prevalence-adjusted and temporally ordered associations among respiratory pathogens in a multicentre hospital surveillance network in China: a retrospective observational study**

## Overview

Respiratory pathogens often circulate concurrently, and more than one pathogen may be detected in the same patient. However, a high observed co-detection frequency does not necessarily indicate a pathogen–pathogen association: frequently circulating pathogens may be detected together simply because each is common. Similarly, detecting pathogen A before pathogen B establishes a temporal ordering, but does not by itself demonstrate that A promotes or inhibits B.

This study examines these questions using a multicentre hospital surveillance network in China. It combines **prevalence-adjusted co-detection analysis**, **temporal validation**, **directional sequential-detection analysis**, and **clinical-outcome comparisons** to characterise epidemiological patterns across respiratory pathogens.

### Study at a glance

| Characteristic | Description |
| --- | --- |
| Study design | Retrospective observational study |
| Setting | 105 hospitals across 16 regions of China |
| Surveillance period | July 2023–April 2026 |
| Study population | 905,757 patients |
| Analytic units | 1,141,715 patient observation windows |
| Pathogens | 29 respiratory pathogens, covering viruses, atypical bacteria, other bacteria, and fungi |
| Main analyses | Co-detection, prevalence-adjusted associations, temporal validation, sequential detection, and clinical outcomes |

**Important:** Pathogen testing was clinically directed rather than uniformly administered. Testing denominators and eligible comparisons therefore differ across pathogens and subgroups.

## Analytical framework

### 1. Observed versus expected co-detection

For two pathogens, A and B, let $P_t(A)$ and $P_t(B)$ denote their observed marginal positivity rates in surveillance interval $t$. Under a statistical-independence benchmark, the expected co-detection rate is:

$$
E_t(A,B) = P_t(A)\,P_t(B).
$$

Observed co-detection rates are compared with this baseline rather than interpreted in isolation. Analyses also describe variation by age, sex, season, geography, and clinical presentation, where corresponding data are available.

### 2. Prevalence-adjusted co-detection (BACR)

To summarise the relationship between observed and independence-expected co-detection over eligible time intervals, the study estimates a **prevalence-adjusted co-detection coefficient (BACR)** using a regression through the origin:

$$
O_t(A,B) \approx \mathrm{BACR}_{A,B}\,E_t(A,B),
$$

where $O_t(A,B)$ is the observed co-detection rate. A BACR above 1 indicates co-detection above the statistical-independence expectation; a BACR below 1 indicates co-detection below that expectation. The corresponding estimate is:

$$
\widehat{O}_t(A,B) = \widehat{\mathrm{BACR}}_{A,B}\,P_t(A)P_t(B).
$$

**BACR is an epidemiological association measure, not evidence of a direct biological interaction.** Its interpretation depends on the observed surveillance population, testing practices, and time-bin eligibility rules.

### 3. Temporal validation

BACR-based estimates are evaluated using a chronological split:

- **Model fitting:** July 2023–June 2025.
- **Held-out evaluation:** July 2025–April 2026.

The figure-level analysis compares estimated and observed co-detection rates in each period. In the reported Figure 4 analysis, Pearson correlations were **0.80** for the fitting period and **0.92** for the temporally held-out period. This evaluates temporal transportability within the surveillance network; it is not a causal validation.

### 4. Temporally ordered pathogen detection

The study separately evaluates ordered detections, written as **A → B**, in which pathogen A is detected before pathogen B within the defined 10-day observation framework. Direction-specific odds ratios and false-discovery-rate (FDR) adjustments are used to identify statistical associations that differ from an odds ratio of 1.

Across **650 evaluable directed pathogen pairs**, **143 associations** met the FDR threshold of 0.05: **127 with odds ratios above 1** and **16 with odds ratios below 1**. These results describe *sequential detection associations* and should not be interpreted as proof that the earlier infection caused the later detection.

### 5. Clinical relevance

The analyses examine how co-detection and ordered detection relate to observed clinical outcomes, including:

- Lower respiratory tract infection (LRTI)
- Hospitalisation
- Intensive care unit (ICU) admission
- Death

Comparisons include age-stratified outcomes, pair-specific observed rates, and selected clinical-outcome risk ratios. All such comparisons are observational and may be influenced by patient characteristics, testing selection, and clinical context.

## Figures

The `pdf/` directory contains the assembled figures associated with the study. The main notebook provides the corresponding figure-level plotting workflow.

| Figure | Description | PDF |
| --- | --- | --- |
| **Figure 1** | Monthly pathogen detections, observed co-detection landscape, and leading pairs by age group | [View Figure 1](pdf/Figure_1.pdf) |
| **Figure 2** | Co-detection versus mono-detection, pair-specific clinical outcomes, and age-stratified risk ratios | [View Figure 2](pdf/Figure_2.pdf) |
| **Figure 3** | BACR framework, prevalence-adjusted pathogen-pair associations, and clinical-outcome comparisons | [View Figure 3](pdf/Figure_3.pdf) |
| **Figure 4** | Temporal validation of BACR-based co-detection estimates and illustrative pathogen pairs | [View Figure 4](pdf/Figure_4.pdf) |
| **Figure 5** | Sequential-detection rates and clinical-outcome profiles across age groups | [View Figure 5](pdf/Figure_5.pdf) |
| **Figure 6** | Directional sequential-detection odds ratios and selected clinical-outcome risk ratios | [View Figure 6](pdf/Figure_6.pdf) |

The [Supplementary Appendix](pdf/Supplementary_appendix.pdf) includes **Tables S1–S4** (pathogen positivity by age, sex, season, and region) and **Figures S1–S9** (geographic distribution, stratified positivity, subgroup analyses, sensitivity analyses, temporal performance, and sequential-detection results).

## Repository structure

```text
respiratory-pathogen-associations/
├── figure_plot.ipynb        # Figure-level analysis and plotting notebook
├── input_manifest.csv       # Mapping of required plot inputs to repository files
├── data/                    # Aggregate figure inputs, matrices, and summaries
│   └── Figure_*/            # Data organised by main or supplementary figure
├── code/                    # Upstream data extraction and cleaning scripts
│   ├── 01_extract_hospital_two_groups.py
│   ├── 02_build_patient_set.py
│   ├── 03_extract_exam.py
│   ├── 04_clean_hospital_two_group.py
│   ├── 05_filter_patient_visits_le15.py
│   └── 06_build_patient_window_deNone_igm.py
└── pdf/                     # Assembled main figures and supplementary appendix
```

The directory names within `data/` correspond to specific main or supplementary figures. Individual CSV files preserve the numerical inputs used for plotting, including rates, summary statistics, matrices, and confidence intervals where applicable.

## Reproducing the figures

1. Clone the repository and enter its root directory:

   ```bash
   git clone https://github.com/linzhang-allan/respiratory-pathogen-associations.git
   cd respiratory-pathogen-associations
   ```

2. Prepare a Python environment with Jupyter and the scientific/plotting dependencies imported by `figure_plot.ipynb`. Exact package versions are not currently pinned in this repository.

3. Launch the notebook **from the repository root**:

   ```bash
   jupyter lab figure_plot.ipynb
   ```

4. Run the notebook cells in order. The notebook reads aggregate inputs under `data/`, with paths resolved through `input_manifest.csv` where applicable, and displays the figure panels.

5. Compare the generated panels with the assembled reference figures under `pdf/`. Minor font, spacing, and PDF-composition differences can occur between rendering environments.

**Scope of reproduction:** The public materials support inspection and regeneration of figures from **provided aggregate inputs**. The underlying patient-level hospital records are not distributed here. The upstream scripts in `code/` document parts of the processing workflow, but they do not by themselves recreate every aggregate input or enable a complete end-to-end rerun without the original clinical data and analysis environment.

## Interpretation and limitations

- **Association is not causation.** BACR, sequential-detection odds ratios, and clinical-outcome risk ratios do not establish pathogen–pathogen interactions or causal effects.
- **Testing was non-uniform.** Positivity denominators vary because pathogen assays were ordered according to clinical circumstances, which may introduce selection and ascertainment biases.
- **Timing matters.** A → B denotes the observed order of detection under the study's window definition, not necessarily the order of infection acquisition.
- **Clinical outcomes are observational.** Differences between groups can reflect underlying illness severity, patient mix, and care settings in addition to pathogen detections.
- **Figure-level reproducibility is distinct from raw-data reproducibility.** The supplied CSVs are aggregate inputs; patient-level records are not included.

## Citation

If you use the data, code, or figure-reproduction resources, please cite the associated study when its bibliographic details become available:

> Zhang L, Li Y, Jin K, et al. *Prevalence-adjusted and temporally ordered associations among respiratory pathogens in a multicentre hospital surveillance network in China: a retrospective observational study.*

The formal journal citation and DOI can be added here following publication.