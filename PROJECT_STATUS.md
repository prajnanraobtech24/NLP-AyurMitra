# AyurMitra project status — 23 October 2026

## Implemented

- FastAPI website with General Ayurveda, Ayurvedic herbs, and Symptoms & conditions search sections.
- English retrieval over WHO and NAMASTE terminology, IMPPAT plant-use associations, and Columbia disease-symptom associations.
- BM25 + TF-IDF search with cached evidence and search indexes. Fast extractive answer mode is the default; Ollama is an optional user-selected mode.
- Source records, provenance details, evidence IDs, abstention behavior, and non-diagnostic safety wording.
- Optional IndicTrans2 adapter, exact loaded-term protection, and input-script hints. Translation is not enabled in this environment.
- Optional NetworkX source graph, dataset audit, and retrieval evaluation script.

## Local data readiness

The latest dataset audit reports:

- WHO: 1,023 prepared chunks covering 606 represented pages.
- NAMASTE: 14,968 terminology rows.
- IMPPAT: 4,154 plant records and 94,261 plant-use associations.
- Columbia: 1,898 associations across 134 disease labels.
- AYUSH register: no reviewed record is currently available. Draft-only content was removed from the active register.

Raw source files and generated indexes are local and git-ignored. A teammate cloning the repository must acquire permitted source files and prepare them locally.

## Runtime checks on this workstation

- FastAPI health, home page, status, and search endpoints returned HTTP 200.
- Warm repeat general search measured about 0.02 seconds after its initial evidence/index build.
- The installed Ollama runtime and configured llama3:latest model are available. On this CPU, one AI-mode search exceeded 120 seconds and fell back. Fast extractive mode is now the default; explicit Ollama calls use a 30-second timeout unless overridden.
- English search is operational. Hindi and Kannada scripts are detected, but translation is unavailable until IndicTrans2 dependencies and weights are installed and validated. Romanized inputs remain heuristic and are searched as typed.

## Research work still required

- Run the planned IndicTrans2 term-corruption go/no-go probe before treating terminology preservation as a supported research premise.
- Verify related work and dataset reuse terms against original sources.
- Build a native-reviewed term/alias inventory and an independently labelled, held-out multilingual query set.
- Compare B0/B1/P1 with controlled settings; run planned ablations and direct multilingual retrieval where feasible.
- Evaluate term preservation, Recall@5/MRR/nDCG, answer support, citations, abstention, human ratings, per-language errors, confidence intervals, latency, and memory.
- No classifier, personalized treatment model, or clinically validated recommendations are implemented. No research accuracy metrics may be claimed until the reviewed evaluation is run.

## Validation

The current suite passes 25 unit tests. The dataset audit reports four required source layers ready. The evaluator returns no metrics because data/evaluation/gold_queries.jsonl is not present. Dense retrieval and IndicTrans2 have not been evaluated in this environment. Ollama was reachable, but the configured 8B model was too slow for practical use here.
