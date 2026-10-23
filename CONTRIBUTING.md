# Contributing to AyurMitra

- Create a branch for a task and keep changes focused.
- Do not commit `.venv`, raw downloads, model weights, secrets, or generated user data.
- Before submitting a change, run:

  ```powershell
  python -m unittest discover -s tests -v
  python scripts\audit_datasets.py
  ```

- If data preparation changes, add a small synthetic *test fixture* under tests (not as a replacement research dataset) and test malformed/missing source cases.
- Document schema assumptions and source provenance. Never infer clinical meaning from a field name alone.
- A dataset fixture used in unit tests must be clearly marked as synthetic and must never enter runtime retrieval.
- Keep patient-facing output cautious, concise, cited, and non-diagnostic.
