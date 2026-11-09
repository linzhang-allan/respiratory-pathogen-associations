# Figure reproduction bundle

- `pdf/` contains the manuscript's six main figure PDFs and the supplementary appendix PDF for visual reference.
- `figure_reproduction.ipynb` collects executable drawing code from `rti_plot_ai/plot_paper.ipynb` and the corresponding figure-generation scripts. Its sections are ordered Figure 1–6 first, then Figure S1–S9. It reproduces the figures and figure panels represented in the PDFs; it keeps the existing plot styles and does not add A/B/C/D panel labels.
- `data/Figure_.../` contains copied, figure-labeled plotting inputs. The bundle uses summarized tables and required geographic boundary data; `input_manifest.csv` records each bundled file's original project path.
- Running all notebook cells displays the plots inline with `plt.show()` and does not write figure or derived table outputs.

Open this notebook from this folder and run all cells with the project's `UTRLM` environment. Input paths are resolved through `input_manifest.csv`, so the original project-only plotting modules are not needed to run the bundled notebook. The source notebook remains at `../plot_paper.ipynb`.
