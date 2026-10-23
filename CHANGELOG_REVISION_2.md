# Revision 2 change log

- Replaced the website's previous retrieval-only response with a grounded RAG pipeline: hybrid retrieval, evidence IDs, local LLM generation when Ollama is configured, and extractive/abstaining fallback otherwise.
- Added BM25 + TF-IDF and optional multilingual sentence-transformer embeddings with FAISS index use when installed.
- Added an optional IndicTrans2 adapter, rough romanized Hindi/Kannada detection, and exact-match NAMASTE terminology protection/restoration.
- Added a source-grounded multi-source NetworkX graph and a manually reviewed AYUSH evidence-register loader.
- Added local dataset status to the website, a dataset audit script, and a retrieval evaluation harness requiring a human-reviewed gold set.
- Added explicit model setup and language-support documentation.
- Preserved original source data and source/license notes. No missing datasets or medical labels were fabricated.
- Automated tests: 22 passing in the local test environment.
