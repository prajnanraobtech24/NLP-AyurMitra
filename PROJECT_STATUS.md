# AyurMitra project status — revision 3

## Delivered in this revision
- Conventional FastAPI website; Streamlit is no longer the primary UI.
- Concise RAG response area, expandable evidence records, source URLs, and local dataset readiness display.
- BM25 + TF-IDF hybrid retrieval; optional multilingual dense embeddings and FAISS integration.
- Optional IndicTrans2 adapter for Hindi/Kannada script workflows and exact-term protection using loaded NAMASTE terms.
- Optional local Ollama RAG generation; extractive evidence-grounded fallback with abstention when evidence does not clearly answer.
- Multi-source NetworkX graph with source provenance and conservative exact-label cross-source links.
- AYUSH manually reviewed evidence-register ingestion, dataset audit utility, retrieval evaluation harness, and tests.

## Local data actually available in this archive
- WHO PDF and extracted WHO text chunks: present.
- NAMASTE, IMPPAT, Columbia data: absent locally during this revision.
- AYUSH portal: no bulk dataset bundled; register template only.

## Do not claim yet
- Hindi/Kannada translation was not executed in the test environment; model installation and validation are still required.
- Dense model/FAISS retrieval and Ollama generation are optional and were not executed in tests.
- No validated supervised disease classifier or personalized herbal recommendation model is present.
- No research performance metrics are claimed until a human-reviewed evaluation set is created and run.

## Validation
`python -m unittest discover -s tests -v` should pass. Use `python scripts/audit_datasets.py` to inspect which local data layers are actually usable.
