# AyurMitra — Start Here (Windows, team edition)

This is the single setup guide for the project. Keep this document with the project folder when sharing it with teammates.

## Before starting

1. Install Python 3.11 or 3.12: https://www.python.org/downloads/windows/ (enable **Add Python to PATH** if offered).
2. Install Git only if your team will use version control: https://git-scm.com/download/win.
3. Extract the full ZIP into a normal folder such as `C:\Projects\AyurMitra`. Do not run the project from inside the ZIP.
4. Open the extracted `AyurMitra_Research_Ready` folder in VS Code.

## One-time setup

1. Double-click `setup_and_run_windows.bat`.
2. The script creates `.venv`, installs the Python packages, attempts to download official datasets that are not already present, prepares the local indexes, audits the data, and launches the website.
3. If it asks whether to configure Ollama, choose **Y** to download the recommended model (about 2 GB) or **N** to use the extractive RAG fallback for now.
4. If Ollama is not detected, install the Windows application from https://ollama.com/download/windows, close/reopen VS Code or the terminal, and double-click `configure_ollama_windows.bat`.
5. When asked about Hindi/Kannada translation, choose **Y** only if you want to install CPU PyTorch/IndicTrans2 now. It is a large optional install; the translation model weights download on first use. Choose **N** to skip and install it later with `configure_translation_windows.bat`.
6. When the server is running, open http://127.0.0.1:8000. Keep the black terminal window open while using the website.

## Ollama: extension vs runtime

The VS Code Ollama extension adds Ollama models to VS Code Chat. It is not a substitute for the Ollama runtime that serves the local API. AyurMitra calls the runtime at `http://localhost:11434`. Install the Windows runtime and pull a model once; the app then reuses that model locally. See https://github.com/ollama/ollama-vscode and https://ollama.com/download/windows.

The provided `configure_ollama_windows.bat` checks for the runtime, downloads `qwen2.5:3b` if needed, and writes `AYURMITRA_OLLAMA_MODEL=qwen2.5:3b` to the project-root `.env`. The model download is a one-time step per computer. A teammate who already has that model does not need to download it again.

## Where source datasets go (exact paths)

The download script uses the paths below. **Do not create new folder names or rename source columns manually.** The prep script reads original files from `data/raw/` and writes derived indexes into `data/processed/`.

| Source | Official link | Exact local destination |
|---|---|---|
| WHO Ayurveda terminology | https://www.who.int/publications/i/item/9789240064935 | Already included: `data/raw/WHO.pdf`; prepared index: `data/processed/who_ayurveda_chunks.jsonl` |
| NAMASTE SAT combined workbook | https://namaste.ayush.gov.in/sat_Ayurveda | `data/raw/namaste_ayurveda_sat_combined.xlsx` |
| IMPPAT 2.0 — plant/use association | https://cb.imsc.res.in/imppat/download | A downloaded table whose filename starts `imppat_plant_therapeutic_use` (keep its actual `.csv`, `.tsv`, `.txt`, `.xlsx`, or `.zip` extension) inside `data/raw/` |
| IMPPAT 2.0 — medicinal plant info | https://cb.imsc.res.in/imppat/download | A downloaded table whose filename starts `imppat_plant_info` (keep its actual extension) inside `data/raw/` |
| Columbia disease/symptom source | https://impact.dbmi.columbia.edu/~friedma/Projects/DiseaseSymptomKB/index.html | `data/raw/columbia_disease_symptom_source.html` only if the saved page contains the actual source table |
| AYUSH Research Portal evidence | https://arp.ayush.gov.in/ | Add reviewed citations only to `data/processed/ayush_evidence_register.csv` using the column layout in `data/ayush_evidence_register_template.csv` |

The first-run downloader tries to obtain the first five source files automatically. For IMPPAT, download **only** the two smaller tables listed above for this project's current scope; do not download the large molecular structure files. If the official site offers a login or terms-of-use screen, follow it rather than bypassing it.

## After any source download

From the VS Code terminal, in the project root (where `requirements.txt` is):

```powershell
.\.venv\Scripts\python.exe scripts\prepare_datasets.py
.\.venv\Scripts\python.exe scripts\audit_datasets.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Open `data/processed/dataset_audit.json`. It records readiness, row/chunk counts, columns, file sizes, hashes, and missing-source actions. If a dataset is marked missing, the related feature cannot use it yet. A download is only accepted if its file signature and schema are plausible; a login/error HTML page is not a dataset.

## Share and continue with teammates

- Share the entire project folder/ZIP, including this guide and `TEAM_HANDOFF.md`.
- Do not commit `.venv/`, `.env`, large model weights, local raw data, passwords, or personal files.
- Source datasets may have non-commercial or no-derivatives terms. Check the current terms before redistributing raw or processed copies. The project can share its download/preparation scripts without bundling restricted source data.
- If multiple team members need identical data, use a university-approved shared location only after checking the source licence. Keep the audit JSON and source hashes with the shared dataset for reproducibility.

## Current capability boundaries

- General Ayurveda: searches local WHO/NAMASTE terminology and explicitly reviewed literature records.
- Ayurvedic herbs: searches locally available IMPPAT plant-use associations.
- Symptoms & conditions: can display general symptom associations and retrieved plant/literature evidence if those datasets are available. It does **not** diagnose, calculate disease probabilities, or make personalized treatment prescriptions.
- English works without translation models. Native-script Hindi/Kannada translation can be enabled with `configure_translation_windows.bat`; the model weights download on first use. Script detection alone is not translation. Hinglish/Kanglish detection is heuristic and is not guaranteed to translate correctly.
- Ollama generation is optional. Without a working local model, the system uses a cautious extractive evidence-based fallback.
