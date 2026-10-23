# Revision 4 changelog — guided website and local RAG setup

- Added three focused website sections: General Ayurveda, Ayurvedic herbs, and Symptoms & conditions. Each section applies its own source filter.
- Added category-aware API requests and a clear safety boundary for symptom/condition exploration.
- Improved structured IMPPAT plant-use summaries so the app can report the source-listed plant/use association without framing it as proof of efficacy or personal medical advice.
- Added citation-index validation for Ollama-generated answers; answers with missing/invalid evidence markers fall back to the extractive grounded path.
- Added `.env` configuration support and Windows helpers to configure the local Ollama runtime/model and optional IndicTrans2 Hindi/Kannada translation.
- Added a single start guide with exact raw dataset filenames and folders, official download links, first-run steps, and team-sharing guidance.
- Clarified that the VS Code Ollama extension is not a replacement for the Windows Ollama runtime used by the website.

## Validation

- `python -m compileall -q app scripts tests` passed.
- `python -m unittest discover -s tests -v`: 24 tests passed.
- FastAPI smoke tests passed for the homepage, health endpoint, dataset status, and all three category-specific search requests.
- Current environment still cannot resolve the official NAMASTE, IMPPAT, or Columbia source hosts; the audit correctly marks those sources as missing rather than inventing records.
