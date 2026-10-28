# Synopsis-to-implementation audit (Revision 2)

> This table records the earlier archive snapshot. For the current workstation's data counts, runtime behavior, and validation, see PROJECT_STATUS.md. The raw source files and prepared indexes are local and git-ignored, so dataset availability differs by machine.

| Synopsis item | Implementation status | Exact limitation / verification needed |
|---|---|---|
| Conventional website | Implemented | FastAPI + HTML/CSS/JS. Streamlit retained as fallback. |
| Concise response and expandable source records | Implemented | Source records and a Sources-used panel are rendered under each response. Citation IDs refer to retrieved evidence order. |
| WHO terminology retrieval | Implemented for the local WHO PDF | WHO PDF and extracted chunks are bundled. PDF table extraction is imperfect in places; review relevant passages before using them as scientific claims. |
| NAMASTE term retrieval | Implemented when workbook is downloaded/prepared | Workbook is absent in this tested archive; no NAMASTE results can appear until added. |
| IMPPAT plant-use retrieval | Implemented for recognized plant/use tables and common-name aliases | Required source tables are absent in this tested archive. Source-use association is not personalized advice. |
| Columbia symptom-condition association lookup | Implemented as transparent text-overlap ranking | Table is absent locally; it is not Ayurveda-specific and no trained classifier is claimed. |
| AYUSH literature catalogue | Evidence-register ingestion implemented | Portal is not treated as a bulk downloadable dataset. Add only manually reviewed records and preserve article-level citations/limitations. |
| Hybrid BM25 + TF-IDF retrieval | Implemented | Lexical baseline works without additional packages. |
| Dense multilingual embeddings + FAISS | Optional integration implemented | Requires optional packages, first-run model download, memory, and empirical comparison. Dense index is built/cached in process, not shipped as a prebuilt index. |
| RAG answer | Implemented with source-first and general-answer paths | Direct extractive answers cite source records. When no direct answer is extractable, Ollama may provide a general educational answer clearly labeled as not based on local records; without Ollama, the app reports that the fallback could not run. Validate citation faithfulness and general-answer quality before publication. |
| IndicTrans2 multilingual translation | Optional integration implemented | Requires model dependencies/weights and explicit environment configuration. It has not been executed in this network-restricted test environment. Hindi/Kannada are not fully operational out of the box. |
| Terminology preservation | Partial implementation | Exact Latin-script terms loaded from NAMASTE are protected around translation. This does not guarantee coverage for all Sanskrit, inflections, or scripts. |
| Hindi, Kannada, romanized/code-mixed input | Partial | Hindi/Kannada script detection is implemented. Romanized identification is a rough heuristic. Tamil/Telugu are detected but no translation route is enabled. |
| Knowledge graph | Implemented from available sources | WHO passage/topic mention edges, NAMASTE term metadata, Columbia symptom-condition associations, IMPPAT 3.0 plant-use associations, provenance fields, and a bounded `/api/knowledge-graph/search` endpoint. Mention and exact-label edges do not imply a medical relationship; no symptom-to-herb recommendations are inferred. |
| Supervised disease classifier | Not implemented / no appropriate labelled dataset bundled | Columbia association rows are not enough to claim a validated Ayurvedic classifier. Requires a licensed, suitable labelled dataset and independent validation. |
| Personalized herb/lifestyle recommendation | Not implemented as clinical advice | IMPPAT is a source-use database. Do not turn those associations into personalized recommendations or dosing. A reviewed evidence protocol is required. |
| Baseline/ablation evaluation | Evaluation harness provided; experiment not run | Add independently labelled `data/evaluation/gold_queries.jsonl`; current environment has no gold labels, so no performance metric is reported. |

## Dataset status from this revision

- WHO PDF and extracted chunks: present and readable.
- NAMASTE workbook: absent.
- IMPPAT source tables: absent.
- Columbia source HTML/prepared table: absent.
- AYUSH reviewed evidence register: template only; no reviewed records.

External source downloads failed in this runtime due to DNS/network access. The app and scripts do not fabricate substitutes for missing datasets. Run the downloader on a network-enabled machine and review the dataset audit before evaluating the full system.
