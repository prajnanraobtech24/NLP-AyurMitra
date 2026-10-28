# Optional multilingual translation setup

## Languages in the application
- English: supported without translation.
- Hindi written in Devanagari: detected by script (other Devanagari languages may be confused); translation requires the optional IndicTrans2 setup.
- Kannada written in Kannada script: detected; translation requires the optional IndicTrans2 setup.
- Romanized Hindi/Hinglish and Kannada/Kanglish: rough keyword heuristic only; language detection is uncertain and translation is not guaranteed.
- Tamil and Telugu scripts: detected but no translation model route is configured in this release.
- Other scripts: accepted as text but not supported by the translation route.

The website's **Answer in** selector offers Auto, English, Hindi, Kannada, Tamil, and Telugu. Auto follows the detected input language when recognized; uncertain romanized input may be misdetected. The answer badge reports the language actually returned, including an English fallback when a requested translation is unavailable.

### Entering a question in another language

Users can type or paste text in a supported script with their operating-system keyboard or an installed input method. The **Voice input** control uses the browser's Web Speech API; choose English, Hindi, Kannada, Tamil, or Telugu before speaking. Voice availability and recognition quality depend on the browser, language pack, microphone permission, and a secure context (localhost is allowed). Voice audio is recognized in the browser and only the resulting text is submitted to AyurMitra. If voice recognition is unavailable, typing and pasting remain available.

When translation is disabled or the model cannot load, the app does not search the English-only corpus as though translation succeeded. IndicTrans2 translates supported Hindi/Kannada input for local retrieval. Without it, Hindi/Kannada queries receive no local search; Ollama may provide a general answer in the requested language, labeled as not based on local records. Romanized input is searched as typed and is not translated. If a source-grounded English answer cannot be translated by IndicTrans2 or Ollama, the app keeps it in English and labels the fallback.

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

Before translating a response, exact Latin-script Sanskrit/Ayurveda terms from the loaded NAMASTE workbook are temporarily replaced with placeholders and restored afterwards. This protects known exact terms in the workbook; it cannot preserve every inflection, spelling, or Sanskrit term absent from the data. Check the source record when precise transliteration or nuance matters.
