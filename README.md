# AyurMitra â€” multilingual, source-grounded Ayurveda knowledge website

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

## Input languages â€” current behaviour

| Input | Current behaviour |
|---|---|
| English | Works immediately with the locally prepared datasets. |
| Hindi in Devanagari | Script is detected. Local English-corpus retrieval requires optional IndicTrans2 setup. Without it, no local search is run; if Ollama is available, a general Hindi answer may be returned and is labeled as not based on local records. |
| Kannada script | Script is detected. Local English-corpus retrieval requires optional IndicTrans2 setup. Without it, no local search is run; if Ollama is available, a general Kannada answer may be returned and is labeled as not based on local records. |
| Romanized Hindi/Hinglish or Kannada/Kanglish | A rough keyword heuristic may identify the language; it is not reliable language identification or translation. General AI fallback requests output in the guessed language; source-grounded extracts remain English. |
| Tamil/Telugu and other scripts | Some scripts are detected for messaging, but local translation routes are not configured. If Ollama is available, a general answer may be generated in the detected language without local evidence. |

See `docs/MULTILINGUAL_SETUP.md` for optional IndicTrans2 installation and the limitations of terminology protection. Do not describe multilingual processing as fully validated until models are installed and tested on a reviewed language test set.

## Retrieval and RAG

- **Hybrid retrieval:** BM25 + TF-IDF by default, with loaded evidence and lexical indexes cached for repeat searches. Optional multilingual sentence-transformer embeddings are opt-in with `AYURMITRA_ENABLE_DENSE=1`; FAISS is used for the dense index when installed. A lightweight lexical fallback always remains available.
- **RAG answer:** source-grounded extraction is tried first. When no direct answer can be extracted, the configured Ollama model may provide a general educational answer, explicitly labeled as not based on local records. Ollama fallback can be slow on CPU; if it is unavailable or exceeds the 45-second default timeout, the app falls back with a clear status. Select Ollama AI mode to use the model for every query.
- **Sources:** each retrieved record includes a source name, record/page detail where available, and source URL. The UI displays the evidence records and a â€œSources usedâ€ panel under the answer.
- **Terminology preservation:** exact Latin-script terms present in the loaded NAMASTE workbook can be temporarily protected around translation. Coverage is limited to terms actually loaded and exact matches; it needs a reviewed test set.
- **Knowledge graph:** includes NAMASTE term nodes, WHO terminology passage/topic mentions, Columbia symptom-condition association edges, and IMPPAT plant-use edges when those datasets exist. Graph search preserves source provenance. Mention and association edges describe dataset contents; they do not infer medical relationships or recommendations.

Optional features:

```powershell
pip install -r requirements\optional_semantic.txt
```

For translation, follow `docs/MULTILINGUAL_SETUP.md`. For local LLM answers, install Ollama and pull a model once. `qwen2.5:3b` is the project setup script's smaller CPU-oriented option; larger models such as `llama3:latest` can be slower. Set `AYURMITRA_OLLAMA_MODEL` in `.env` to the model you installed, then restart Uvicorn. Ollama's local server must be running. Interactive requests use a 45-second timeout by default so a slow CPU model can fall back to the source-grounded answer; increase `AYURMITRA_OLLAMA_TIMEOUT_SECONDS` in `.env` if your hardware needs more time.

## Database status â€” important

On this workstation, the latest audit reports WHO, NAMASTE, IMPPAT, and Columbia data ready. AYUSH has no reviewed record. Raw source files and generated indexes are git-ignored, so another clone will need to acquire permitted files and prepare its own indexes. Read data/processed/dataset_audit.json for the machine-specific status; a missing source is not an empty or negative clinical result.

- **WHO:** terminology/document retrieval; not a disease-training dataset.
- **NAMASTE:** official standardized terminology workbook; not patient-level symptom labels.
- **IMPPAT 3.0:** plant-part/therapeutic-use association tables; not individualized efficacy/safety evidence.
- **Columbia Diseaseâ€“Symptom Knowledge Database:** general clinical associations, not Ayurveda-specific and not a supervised model by itself.
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

AyurMitra does not diagnose, prescribe, give dosages, or provide personalized treatment advice. A textual association is not a probability or proof of clinical efficacy. No suitable labelled dataset for the complete symptom â†’ Ayurvedic condition â†’ individualized recommendation chain is currently bundled, so this version does **not** claim a trained disease classifier. Herbal records are source-listed uses only; safety and clinical claims require independent review.
