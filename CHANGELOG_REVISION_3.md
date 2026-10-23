# Revision 3 changelog — dataset acquisition and team handoff

- Updated Columbia source acquisition to try the current `impact.dbmi.columbia.edu` host first and the legacy `people.dbmi.columbia.edu` host second.
- Added source-content checks before accepting the Columbia HTML page.
- Added more careful official NAMASTE workbook validation and a fallback filename for manually downloaded SAT-COMBINED workbooks.
- Strengthened IMPPAT download-link parsing for normal links, data attributes and common JavaScript download buttons.
- Improved alternate Columbia table parsing so the output uses the exact disease/symptom schema consumed by the application rather than saving an unnormalized table.
- Expanded dataset audit with raw file sizes, SHA-256 hashes, schema/row counts, required-vs-optional missing sources and specific next actions.
- Made the Windows setup script attempt download → preparation → audit automatically before launching the website.
- Added `TEAM_HANDOFF.md` and `CONTRIBUTING.md` for shared project continuity, data/licence handling, and reproducible setup.
- Rewrote `docs/DATA_SOURCES.md` as a source-specific acquisition and validation guide.

## Validation performed

- `python -m unittest discover -s tests -v`: 22 tests passed.
- FastAPI smoke checks: `/`, `/api/health`, `/api/status`, `/api/knowledge-graph`, and an English `/api/search` request returned HTTP 200.
- `python scripts/prepare_datasets.py`: WHO index rebuilt with 1,023 chunks across 608 pages.
- `python scripts/audit_datasets.py`: correctly reports WHO ready and NAMASTE, IMPPAT, and Columbia missing in this build environment. The build environment could not resolve those source hosts; the downloader will retry them when run by a team member with internet access.

## Important non-claim

Revision 3 improves dataset acquisition, validation, provenance and handoff. It does not falsely claim that unavailable source files were downloaded. The audit must show a source as ready before the team describes it as locally available or evaluates against it.
