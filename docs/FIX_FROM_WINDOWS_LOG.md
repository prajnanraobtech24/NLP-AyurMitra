# Fix for the Windows dataset-download log

Your previous run did the following successfully:
- Columbia: 1,898 disease–symptom associations across 134 disease labels.
- NAMASTE: 14,968 terminology rows.
- IMPPAT plant information: downloaded (541,093 bytes).

It did **not** complete WHO or IMPPAT plant-use data:
- WHO returned a 755-byte HTML error page rather than a PDF.
- IMPPAT's plant-info table is not the same file as the required Plant - Therapeutic use Association table.

## What was corrected in this project

1. WHO downloader now tries the current official WHO publication-page API endpoint and discovers download links even when the URL has no `.pdf` suffix.
2. WHO file validation checks the actual `%PDF` signature and removes an invalid HTML placeholder instead of letting it look like a PDF.
3. IMPPAT download matching ignores punctuation in labels. The old code searched for `plant therapeutic use association` as one contiguous phrase, but the page label is `Plant - Therapeutic use Association`, so it missed the row.
4. IMPPAT matching now prioritizes the exact table row and inspects common download button attributes.
5. Added network-free tests for these parsing fixes.

## Apply without losing the files already downloaded

Extract the updated ZIP into the **existing parent folder** that contains `AyurMitra_Research_Ready`, and choose **Replace files** when Windows asks. This merges updated scripts/docs into the existing project; it does not delete your `data/raw` files.

Your current folder should be:
`AyurMitra_Final_Source_Integrated_Project\AyurMitra_Research_Ready`

Then in PowerShell, from that folder, run:

```powershell
python -m unittest discover -s tests -v
python scripts\download_datasets.py
python scripts\prepare_datasets.py
streamlit run app\streamlit_app.py
```

## If either official site still blocks automated download

### WHO PDF
1. Open https://www.who.int/publications/i/item/9789240064935
2. Click **Download (4.4 MB)**.
3. Save the real PDF as `data/raw/who_ayurveda_terminologies.pdf` or keep the original working name `data/raw/WHO.pdf`. Both names are supported.
4. Confirm it opens in a PDF reader. Do not rename a web error page to `.pdf`.

### IMPPAT plant-use association table
1. Open https://cb.imsc.res.in/imppat/download
2. Download **Plant - Therapeutic use Association** (about 6.2 MB).
3. Save the original file under `data/raw/` with a name starting `imppat_plant_therapeutic_use`, preserving its actual extension.
4. Keep the already downloaded `imppat_plant_info.csv`.

Finally run `python scripts\prepare_datasets.py` again. The project is fully source-ready only when WHO text chunks and the IMPPAT plant-use association table are both detected.

**Important:** This build environment cannot access the external internet, so I can test the downloader's parsing and validation logic but cannot claim a successful live download from your laptop's network. Do not use this app as a diagnostic or treatment tool.


### Reference from the initial project ZIP
The initial project used `data/raw/WHO.pdf` and extracted text with `pypdf`. The updated downloader and preparation code now recognizes that filename, validates that it is a real PDF, reuses it without trying to download over it, and creates `data/processed/who_ayurveda_chunks.jsonl`. The reference WHO PDF has been included in this corrected project archive.

## Follow-up fix: IMPPAT recognition and common-name search

The app may download the IMPPAT plant–therapeutic-use association CSV successfully but still show it as unavailable if the official export uses the column name `Indian medicinal plant`. The app now recognizes that official column, preserves reference strings, and uses common/synonymous names from the IMPPAT plant-information table for search matching (for example, a common-name query such as “Ashwagandha” can match the scientific plant name when the alias exists in the source table).

The Dataset readiness indicator now reflects whether usable plant/use rows can be parsed, not merely whether a file exists. A no-match message for NAMASTE is not necessarily a data failure: NAMASTE standardizes Ayurveda terminology and is not a dedicated medicinal-plant-use database.


## IMPPAT CSV delimiter fix (15 October 2026)

The downloaded files named `imppat_plant_therapeutic_use.csv` and `imppat_plant_info.csv` may actually be tab-delimited. Their headers can appear as one long field when loaded with the default comma delimiter, which makes Dataset readiness show IMPPAT as unavailable. The current `app/core.py` inspects the header and detects tabs even when the filename ends in `.csv`. The test suite includes an official-header, tab-delimited fixture. Keep both source files in `data/raw/`; no re-download is needed.
