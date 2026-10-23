# AyurMitra — multilingual, source-grounded Ayurveda knowledge website

> **Start here:** Read [`docs/START_HERE_WINDOWS.md`](docs/START_HERE_WINDOWS.md) first. It explains installation, the three website sections, Ollama setup, exact dataset destinations, and team handoff.


AyurMitra is a research prototype for terminology-preserving multilingual retrieval over Ayurveda reference sources. It uses a conventional website (HTML/CSS/JavaScript) served by FastAPI; Streamlit is retained only as a fallback. The implementation now includes hybrid retrieval, source-grounded RAG, an evidence/source panel, a provenance-preserving knowledge graph, data-readiness reporting, and optional translation/dense retrieval/local LLM integrations.

## Run on Windows

1. Install Python 3.11 or 3.12.
2. Extract this folder and double-click `setup_and_run_windows.bat`.
3. The script installs dependencies, attempts official dataset downloads, prepares local indexes, runs the dataset audit, and then starts the website. Dataset downloads need internet access; some sources may block automated downloads.
4. Open `http://127.0.0.1:8000`.
5. If the audit reports missing sources, read `data/processed/dataset_audit.json` and follow the exact source-specific action in `docs/DATA_SOURCES.md`.

Manual PowerShell setup:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python scripts\download_datasets.py
python scripts\prepare_datasets.py
python scripts\audit_datasets.py
python -m uvicorn app.web_app:app --reload
```

The browser UI is at `http://127.0.0.1:8000`; API docs are at `http://127.0.0.1:8000/docs`; dataset status is at `/api/status`; knowledge-graph counts are at `/api/knowledge-graph`.

## Input languages — current behaviour

| Input | Current behaviour |
|---|---|
| English | Works immediately with the locally prepared datasets. |
| Hindi in Devanagari | Script is detected. Actual translation/retrieval requires the optional IndicTrans2 model setup. Without it, the app clearly reports translation unavailable and does not pretend to search the English corpus. |
| Kannada script | Script is detected. Actual translation/retrieval requires the optional IndicTrans2 model setup. Without it, the app clearly reports translation unavailable. |
| Romanized Hindi/Hinglish or Kannada/Kanglish | Only a rough keyword heuristic is available; it searches the typed text as-is. It is not reliable language identification or guaranteed translation. |
| Tamil/Telugu and other scripts | Some scripts are detected for messaging, but translation routes are not configured in this release. |

See `docs/MULTILINGUAL_SETUP.md` for optional IndicTrans2 installation and the limitations of terminology protection. Do not describe multilingual processing as fully validated until models are installed and tested on a reviewed language test set.

## Retrieval and RAG

- **Hybrid retrieval:** BM25 + TF-IDF by default. Optional multilingual sentence-transformer embeddings are used when the optional packages/model are available; FAISS is used for the dense index when installed. A lightweight lexical fallback always remains available.
- **RAG answer:** when `AYURMITRA_OLLAMA_MODEL` names a locally installed Ollama model, the system asks it to answer only from retrieved evidence and cite evidence IDs. Otherwise it uses a concise extractive grounded fallback and abstains when it cannot find a defensible passage. This fallback is not a general-purpose generative LLM.
- **Sources:** each retrieved record includes a source name, record/page detail where available, and source URL. The UI displays the evidence records and a “Sources used” panel under the answer.
- **Terminology preservation:** exact Latin-script terms present in the loaded NAMASTE workbook can be temporarily protected around translation. Coverage is limited to terms actually loaded and exact matches; it needs a reviewed test set.
- **Knowledge graph:** includes NAMASTE term nodes, Columbia symptom-condition association edges, and IMPPAT plant-use edges when those datasets exist. Cross-source links are made only for exact normalized label matches and explicitly labelled as such; they are not inferred medical relationships.

Optional features:

```powershell
pip install -r requirements\optional_semantic.txt
```

For translation, follow `docs/MULTILINGUAL_SETUP.md`. For local LLM answers, install Ollama, run `ollama pull qwen2.5:3b`, then set `$env:AYURMITRA_OLLAMA_MODEL = "qwen2.5:3b"` in PowerShell before starting Uvicorn. This activates the generation path; without it, the app uses the extractive fallback. These optional model weights can require substantial disk space and memory.

## Database status — important

The archive includes the valid WHO Ayurveda terminology PDF and extracted text chunks. The NAMASTE workbook, IMPPAT plant-use tables, and Columbia association table were **not present locally** when this revision was built. This build environment could not resolve the external source hosts, so those original files could not be downloaded and bundled here. The setup script attempts official downloads on each team member’s computer, then prepares and audits them. The app cannot query a source that is not present; `data/processed/dataset_audit.json` states the actual readiness for the local machine. The UI reports the real readiness of each source; do not treat a missing source as an empty/negative clinical result.

- **WHO:** terminology/document retrieval; not a disease-training dataset.
- **NAMASTE:** official standardized terminology workbook; not patient-level symptom labels.
- **IMPPAT 2.0:** plant-part/therapeutic-use association tables; not individualized efficacy/safety evidence.
- **Columbia Disease–Symptom Knowledge Database:** general clinical associations, not Ayurveda-specific and not a supervised model by itself.
- **AYUSH Research Portal:** a literature catalogue, not a verified bulk corpus. Only manually reviewed records added to `data/processed/ayush_evidence_register.csv` are indexed; template at `data/ayush_evidence_register_template.csv`.

Follow `TEAM_HANDOFF.md` for team onboarding and `docs/DATA_SOURCES.md` for official source links, expected files, licence cautions, and manual download steps. Run `python scripts\audit_datasets.py` after preparing the source files. The raw files and their SHA-256 hashes are recorded by the audit for reproducibility.

## Evaluation and tests

```powershell
python -m unittest discover -s tests -v
python scripts\audit_datasets.py
python scripts\evaluate_retrieval.py
```

The retrieval evaluator requires a human-reviewed gold file at `data/evaluation/gold_queries.jsonl`. It intentionally reports no accuracy when no independently labelled gold set exists. Do not publish fabricated accuracy, disease-classifier metrics, or translation performance.

## Medical/research limitations

AyurMitra does not diagnose, prescribe, give dosages, or provide personalized treatment advice. A textual association is not a probability or proof of clinical efficacy. No suitable labelled dataset for the complete symptom → Ayurvedic condition → individualized recommendation chain is currently bundled, so this version does **not** claim a trained disease classifier. Herbal records are source-listed uses only; safety and clinical claims require independent review.
