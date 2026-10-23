# Optional multilingual translation setup

## Languages in the application
- English: supported without translation.
- Hindi written in Devanagari: detected; translation requires the optional IndicTrans2 setup.
- Kannada written in Kannada script: detected; translation requires the optional IndicTrans2 setup.
- Romanized Hindi/Hinglish and Kannada/Kanglish: rough keyword heuristic only; language detection is uncertain and translation is not guaranteed.
- Tamil and Telugu scripts: detected but no translation model route is configured in this release.
- Other scripts: accepted as text but not supported by the translation route.

## Enable IndicTrans2

**Windows shortcut:** first run the main setup so `.venv` exists, then double-click `configure_translation_windows.bat`. It installs CPU PyTorch and `requirements/optional_translation.txt`, then sets `AYURMITRA_TRANSLATION=indictrans2` in the project-root `.env`.

Manual route:
1. Use Python 3.11/3.12 in the project virtual environment.
2. Install a suitable PyTorch build, then run `pip install -r requirements/optional_translation.txt`.
3. Set `AYURMITRA_TRANSLATION=indictrans2` in `.env` before starting Uvicorn.
4. On first translation, the AI4Bharat IndicTrans2 model weights are downloaded from Hugging Face and may require several GB of disk space/RAM. Models used are `ai4bharat/indictrans2-indic-en-1B` and `ai4bharat/indictrans2-en-indic-1B`.
5. Restart the app and test Hindi and Kannada queries. If the model cannot load, the app explicitly reports translation unavailable rather than silently treating the text as English.

Example PowerShell:

```powershell
$env:AYURMITRA_TRANSLATION = "indictrans2"
python -m uvicorn app.web_app:app --reload
```

## Terminology preservation

Before translation, exact Latin-script terms present in the loaded NAMASTE workbook are temporarily replaced with placeholders and restored after translation. This protects only terms found in the loaded workbook and exact-matched in the input; it is not a guarantee that every Sanskrit/Ayurveda term is protected. The translated output must be evaluated on a manually reviewed test set before reporting research results.
