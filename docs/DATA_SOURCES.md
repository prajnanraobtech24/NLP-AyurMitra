# AyurMitra dataset register and acquisition guide

Run `python scripts/download_datasets.py`, then `python scripts/prepare_datasets.py`, then `python scripts/audit_datasets.py`. On Windows, `setup_and_run_windows.bat` attempts these steps automatically before launching the website.

The project deliberately does not bundle source datasets whose redistribution rights are unclear or restricted. The audit reports whether a source is genuinely usable; missing data are never fabricated.

## 1. WHO — International Standard Terminologies on Ayurveda

- Official page: https://www.who.int/publications/i/item/9789240064935
- Official page identifies a 588-page PDF, published 10 January 2023. The PDF already included in this archive is saved as `data/raw/WHO.pdf`; the processor supports both this legacy name and `data/raw/who_ayurveda_terminologies.pdf`.
- Prepared index: `data/processed/who_ayurveda_chunks.jsonl`.
- Purpose: terminology/document retrieval, not labelled symptom-disease training data.
- Licence stated on the WHO publication page: CC BY-NC-SA 3.0 IGO. Preserve attribution and comply with non-commercial/share-alike conditions.

## 2. NAMASTE — Ayurveda Standardized Terminologies (SAT)

- Official portal: https://namaste.ayush.gov.in/sat_Ayurveda
- Current combined Excel link exposed by the official portal: https://namaste.ayush.gov.in/admin/assets/excel/namaste/ayu_sat_table_combined.xlsx
- Expected raw file: `data/raw/namaste_ayurveda_sat_combined.xlsx`.
- Prepared index: `data/processed/namaste_ayurveda_terminology.csv`. The original sheet name is retained as `source_sheet`; official labels/codes/definitions are not intentionally rewritten.
- Purpose: standardized terminology/code/definition/reference lookup. It is not patient-level symptom data and is not itself a disease-prediction training set.
- If automated download fails: open the official portal, use **SAT-COMBINED as MS-Excel File**, and save the actual workbook to the expected path. Do not save the HTML page/login response with an `.xlsx` extension.
- Check the current portal terms before redistributing the workbook or derived data.

## 3. IMPPAT 2.0 — Indian Medicinal Plants, Phytochemistry And Therapeutics

- Official database: https://cb.imsc.res.in/imppat/
- Official batch-download page: https://cb.imsc.res.in/imppat/download
- Required smaller source tables: **Plant - Therapeutic use Association** (listed as about 6.2 MB on the page) and **Information on Medicinal Plants in IMPPAT** (listed as about 529 KB). These are sufficient for the current plant/use search and common-name matching. Do not download the much larger molecular structure/target files unless the scope explicitly requires them.
- Expected filename prefixes: `data/raw/imppat_plant_therapeutic_use.*` and `data/raw/imppat_plant_info.*`. Keep the original file format/extension; supported formats include CSV/TSV/TXT, XLS/XLSX, and ZIP containing a tabular file.
- The loader detects tab-delimited exports even if their extension says `.csv`, adapts source column names, and joins common names only through normalized plant-name matches.
- Purpose: source-listed plant-part and therapeutic-use associations. It does not prove effectiveness or safety for a specific person.
- The official download page states CC BY-NC-ND 4.0 and a research-only disclaimer. Check the current licence before redistributing or creating adapted datasets; the project ZIP does not redistribute these source files.
- If automatic link discovery fails: download the two tables from the official batch page and save them locally using the filename prefixes above. Then rerun preparation and audit.

## 4. Columbia University Disease–Symptom Knowledge Database

- Current host attempted first: https://impact.dbmi.columbia.edu/~friedma/Projects/DiseaseSymptomKB/index.html
- Legacy host attempted as fallback: https://people.dbmi.columbia.edu/~friedma/Projects/DiseaseSymptomKB/index.html
- The downloader validates that the response looks like the expected disease/symptom source before saving it to `data/raw/columbia_disease_symptom_source.html`.
- Prepared index: `data/processed/columbia_disease_symptom.csv`, with normalized disease and symptom columns, codes and provenance.
- Background: Wang X, Chused A, Elhadad N, Friedman C, Markatou M. “Automated knowledge acquisition from clinical narrative reports.” AMIA Annual Symposium Proceedings, 2008, pp. 783–787; PMCID: PMC2656103.
- The source describes general clinical disease-symptom associations derived from discharge summaries. It is not Ayurveda-specific and is not, by itself, a patient-level supervised training dataset or validated classifier.
- The reuse licence is not clearly stated on the source page; confirm permission before redistributing/publishing derived data. Do not substitute a random public mirror without reviewing its provenance and licence.
- If the source host is unavailable, keep this source marked missing rather than creating rows manually.

## 5. AYUSH Research Portal

- Official portal: https://arp.ayush.gov.in/
- About page: https://arp.ayush.gov.in/researchabout
- This is a research/publication catalogue; it is not assumed to provide a general-purpose bulk dataset. The project includes a review-register template at `data/ayush_evidence_register_template.csv`. Only manually reviewed records with full citation and source URL should be added to `data/processed/ayush_evidence_register.csv`.
- Do not scrape or redistribute records without checking the portal's terms. A publication abstract is not proof of a treatment claim for an individual user.

## Verify every source after download

1. Run `python scripts/prepare_datasets.py`.
2. Run `python scripts/audit_datasets.py`.
3. Open `data/processed/dataset_audit.json`. It records usable readiness, row/chunk counts, columns, raw file sizes and SHA-256 hashes, plus actions for missing sources.
4. Run `python -m unittest discover -s tests -v`.

A source is not “ready” merely because a file exists. Its data must parse into the expected schema and produce usable records.

## Critical scientific boundary

No identified source directly validates the complete chain “free-text symptoms → Ayurvedic diagnosis → personalized herb/lifestyle recommendation.” Keep WHO/NAMASTE terminology, general clinical associations, IMPPAT plant/use associations, and reviewed literature evidence as separate evidence layers. Do not call textual overlap a probability, do not claim a trained classifier without appropriate licensed labels and independent evaluation, and do not present source-listed plant uses as individualized medical advice.
