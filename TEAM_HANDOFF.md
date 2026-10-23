# AyurMitra team handoff

This file is the starting point for every new team member. Keep the project reproducible and do not rely on one person's laptop, local files, or environment variables.

## First run (Windows)

For a complete step-by-step walkthrough with exact source file destinations and Ollama configuration, start with [`docs/START_HERE_WINDOWS.md`](docs/START_HERE_WINDOWS.md).

1. Install Python 3.11 or 3.12 and ensure the Python launcher (`py`) is available.
2. Extract the whole project folder to a normal writable location.
3. Double-click `setup_and_run_windows.bat`.
4. Open `http://127.0.0.1:8000` after the console says the server is running.
5. Review `data/processed/dataset_audit.json`. The `ready` fields are authoritative for that computer. If a source is missing, follow its `next_actions` entry and `docs/DATA_SOURCES.md`.

The first run needs internet access to install Python packages and attempt the official source downloads. Ollama local generation can be enabled with `configure_ollama_windows.bat`; it downloads the recommended model only once per computer. Optional multilingual translation/embedding weights require separate setup and are not enabled just because a language script is detected.

## What is and is not shared

- Source code, scripts, tests, documentation, and the existing WHO-derived text chunks are in the project archive.
- Raw source files for NAMASTE, IMPPAT and Columbia are deliberately not bundled because access, terms, or redistribution rights can change or may not permit redistribution.
- Raw and processed local data are git-ignored by default. Each teammate should use the downloader and audit locally. If the supervisor approves a shared dataset folder, distribute it only through an approved university location and include the source licence, retrieval date, and SHA-256 hashes.
- Never add API keys, passwords, local absolute paths, or personal data to the repository.

## Reproducible workflow

Run from the project root (the folder containing `app`, `scripts`, and `requirements.txt`):

```powershell
python -m pip install -r requirements.txt
python scripts\download_datasets.py
python scripts\prepare_datasets.py
python scripts\audit_datasets.py
python -m unittest discover -s tests -v
python scripts\evaluate_retrieval.py
```

`audit_datasets.py` returns exit code 2 when required sources are still missing. This is an honest readiness signal, not a software crash. `dataset_audit.json` records file sizes and SHA-256 hashes so teammates can check whether their local files match.

## Team rules

1. Do not replace a failed download with a random mirror or a synthetic dataset without approval and a documented source/licence review.
2. Keep the original source files unchanged. Preparation scripts should write derived files under `data/processed/`.
3. Do not report a database as ready unless the audit confirms usable rows and the required schema.
4. Do not call Columbia symptom overlap a trained disease classifier. It is a general clinical association resource and is not Ayurveda-specific.
5. Do not present IMPPAT source-listed plant uses as proof of clinical effectiveness or individualized treatment recommendations.
6. Every generated RAG answer must be grounded in returned evidence; retain source title, URL, page/record details, and limitations.
7. Any new model or dataset must have a documented licence, version, download location, retrieval date, preprocessing procedure, and tests.
8. Do not publish performance numbers until the gold evaluation queries have been independently reviewed and the evaluation script has run.

## Current language and model state

The website has separate General Ayurveda, Ayurvedic herbs, and Symptoms & conditions sections. English is the default end-to-end path. Hindi/Kannada translation, multilingual dense retrieval, and local Ollama generation are optional components and must be configured and tested before describing them as enabled. See `docs/MULTILINGUAL_SETUP.md` and `README.md`.

## Suggested ownership split

- Data lead: official download access, schema review, source manifest, licence and integrity audit.
- Retrieval/RAG lead: chunking, hybrid retrieval, answer grounding, citation correctness, abstention tests.
- Multilingual lead: translation setup, terminology protection, reviewed English/Hindi/Kannada and romanized test cases.
- Evaluation/documentation lead: gold query set, metrics, ablations, error analysis, paper-ready reproducibility notes.

All changes should be committed in small, reviewed steps with tests. A new member should be able to reproduce the setup from this document without private instructions.
