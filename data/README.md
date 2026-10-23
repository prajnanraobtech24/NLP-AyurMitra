# Data directory policy

- `raw/`: original downloaded files. Keep them unchanged. Each dataset's terms may prohibit redistribution, so these files are ignored by Git by default.
- `processed/`: derived indexes and `dataset_audit.json`. These are regenerated from local source files; do not manually edit derived indexes as the source of truth.
- `evaluation/`: human-reviewed gold queries and evaluation notes. Do not add synthetic examples to the runtime corpus.
- `source_manifest.json`: official source URLs, expected local filenames, purposes, and licensing notes.

Run the download, prepare, and audit scripts from the project root. `dataset_audit.json` includes SHA-256 hashes and readiness. Share data with teammates only through a supervisor-approved location and only after checking the current licence.
