# Figure reproduction bundle

- `pdf/` contains the manuscript's six main figure PDFs and the supplementary appendix PDF for visual reference.
- All Python imports are in the first code cell. The saved notebook contains outputs from a successful run of all 40 code cells, including 29 inline plots.
- `figure_reproduction.ipynb` collects executable drawing code from `rti_plot_ai/plot_paper.ipynb` and the corresponding figure-generation scripts. Its sections are ordered Figure 1–6 first, then Figure S1–S9. It reproduces the figures and figure panels represented in the PDFs; it keeps the existing plot styles and does not add A/B/C/D panel labels.
- `data/Figure_.../` contains the 93 files loaded by the notebook, organized by figure. The bundle uses summarized tables and required geographic boundary data; `input_manifest.csv` records original project paths for these inputs (including repeated mappings where needed).
- Running all notebook cells displays the plots inline with `plt.show()` and does not write figure or derived table outputs.

Open this notebook from this folder and run all cells with the project's `UTRLM` environment to reproduce the plots. Input paths are resolved through `input_manifest.csv`, so the original project-only plotting modules are not needed to run the bundled notebook. The source notebook remains at `../plot_paper.ipynb`.
