from __future__ import annotations
import json, re, sys
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)


def clean_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def split_umls_term(value: str):
    """Parse UMLS:Cxxxx_label; keep the code and display label as separate fields."""
    value = clean_text(value)
    match = re.match(r"(?:UMLS:)?([A-Z]\d+)_?(.*)", value)
    if match:
        return match.group(1), clean_text(match.group(2)).replace("_", " ")
    return "", value


def prepare_columbia() -> int:
    source = RAW / "columbia_disease_symptom_source.html"
    if not source.exists():
        print("[skip] Columbia HTML missing; run scripts/download_datasets.py first")
        return 0
    soup = BeautifulSoup(source.read_text(encoding="utf-8", errors="replace"), "html.parser")
    table = None
    for t in soup.find_all("table"):
        text = " ".join(t.stripped_strings).lower()
        if "disease" in text and "symptom" in text and ("occurrence" in text or "count" in text):
            table = t
            break
    if table is None:
        # Fallback for page versions whose source table is rendered with a different HTML layout.
        # Normalize the table into the exact schema consumed by the app; never save a raw
        # unrelated table and call it ready.
        try:
            tables = pd.read_html(str(source))
            for raw_df in tables:
                if len(raw_df.columns) < 3:
                    continue
                df = raw_df.copy().fillna("")
                colmap = {str(c).strip().lower(): c for c in df.columns}
                disease_col = next((c for k,c in colmap.items() if "disease" in k), None)
                symptom_col = next((c for k,c in colmap.items() if "symptom" in k), None)
                count_col = next((c for k,c in colmap.items() if "count" in k or "occurrence" in k), None)
                if disease_col is None or symptom_col is None:
                    continue
                rows=[]
                for _, row in df.iterrows():
                    disease = clean_text(row.get(disease_col, ""))
                    symptom_cell = clean_text(row.get(symptom_col, ""))
                    count = clean_text(row.get(count_col, "")) if count_col else ""
                    if not disease or not symptom_cell:
                        continue
                    dcode,dlabel=split_umls_term(disease)
                    for part in symptom_cell.split("^"):
                        scode,slabel=split_umls_term(part)
                        if slabel:
                            rows.append({"disease_raw":disease,"disease_code":dcode,"disease":dlabel or disease,
                                         "disease_count_in_source":count,"symptom_raw":part,"symptom_code":scode,
                                         "symptom":slabel,"source":"Columbia Disease-Symptom Knowledge Database",
                                         "source_url":"https://impact.dbmi.columbia.edu/~friedma/Projects/DiseaseSymptomKB/index.html"})
                result=pd.DataFrame(rows).drop_duplicates()
                if not result.empty:
                    target=OUT / "columbia_disease_symptom.csv"
                    result.to_csv(target,index=False)
                    print(f"[prepared] {target.relative_to(ROOT)}: {len(result)} disease-symptom associations via alternate table parser")
                    return len(result)
        except Exception as exc:
            print(f"[error] Could not parse Columbia table: {exc}")
        print("[error] Could not find an expected, usable disease-symptom table in the Columbia page")
        return 0
    rows=[]
    current_disease=""
    current_count=""
    for tr in table.find_all("tr"):
        cells=tr.find_all(["th","td"])
        if len(cells) < 3:
            continue
        vals=[clean_text(c.get_text(" ", strip=True)) for c in cells[:3]]
        if vals[0].lower() == "disease" or vals[2].lower() == "symptom":
            continue
        if vals[0]: current_disease=vals[0]
        if vals[1]: current_count=vals[1]
        if not current_disease or not vals[2]: continue
        dcode,dlabel=split_umls_term(current_disease)
        # Some symptom cells contain multiple equivalent UMLS terms separated by ^.
        for part in vals[2].split("^"):
            scode,slabel=split_umls_term(part)
            if slabel:
                rows.append({"disease_raw":current_disease,"disease_code":dcode,"disease":dlabel or current_disease,
                             "disease_count_in_source":current_count,"symptom_raw":part,"symptom_code":scode,"symptom":slabel,
                             "source":"Columbia Disease-Symptom Knowledge Database","source_url":"https://impact.dbmi.columbia.edu/~friedma/Projects/DiseaseSymptomKB/index.html"})
    df=pd.DataFrame(rows).drop_duplicates()
    if df.empty:
        print("[error] Columbia parser returned no associations; source layout may have changed")
        return 0
    target=OUT / "columbia_disease_symptom.csv"
    df.to_csv(target,index=False)
    print(f"[prepared] {target.relative_to(ROOT)}: {len(df)} disease-symptom associations, {df['disease'].nunique()} distinct disease labels")
    return len(df)


def find_who_pdf():
    """Support both the current filename and the initial project's WHO.pdf name."""
    for candidate in (RAW / "who_ayurveda_terminologies.pdf", RAW / "WHO.pdf"):
        try:
            if candidate.is_file() and candidate.stat().st_size > 100_000 and candidate.read_bytes()[:5] == b"%PDF-":
                return candidate
        except OSError:
            continue
    return None


def prepare_who_chunks() -> int:
    pdf=find_who_pdf()
    if pdf is None:
        print("[skip] No valid WHO Ayurveda terminology PDF found. Put the actual PDF in data/raw/ as WHO.pdf or who_ayurveda_terminologies.pdf, or run scripts/download_datasets.py.")
        return 0
    try:
        reader=PdfReader(str(pdf))
        chunks=[]
        for page_no,page in enumerate(reader.pages, start=1):
            text=clean_text(page.extract_text() or "")
            if not text: continue
            # Split into moderate-size text blocks for laptop-friendly TF-IDF retrieval.
            words=text.split()
            for start in range(0,len(words),180):
                chunk=" ".join(words[start:start+180])
                if len(chunk) > 40:
                    chunks.append({"page":page_no,"chunk_id":len(chunks)+1,"text":chunk,
                                   "source":"WHO international standard terminologies on Ayurveda (2022)",
                                   "source_url":"https://www.who.int/publications/i/item/9789240064935"})
        if not chunks:
            print("[error] No extractable text found in WHO PDF; check that the PDF downloaded correctly")
            return 0
        target=OUT / "who_ayurveda_chunks.jsonl"
        with target.open("w",encoding="utf-8") as f:
            for chunk in chunks: f.write(json.dumps(chunk,ensure_ascii=False)+"\n")
        print(f"[prepared] {target.relative_to(ROOT)}: {len(chunks)} searchable text chunks from {len(reader.pages)} pages")
        return len(chunks)
    except Exception as exc:
        print(f"[error] Could not extract WHO PDF: {exc}")
        return 0



def prepare_namaste() -> int:
    """Convert the official NAMASTE Ayurveda combined workbook to a searchable CSV."""
    candidates = [RAW / "namaste_ayurveda_sat_combined.xlsx", RAW / "ayu_sat_table_combined.xlsx"]
    source = next((p for p in candidates if p.exists() and p.stat().st_size > 10_000 and p.read_bytes()[:2] == b"PK"), None)
    if source is None:
        print("[skip] NAMASTE workbook missing or invalid; run scripts/download_datasets.py first. Expected a real .xlsx workbook, not an HTML login/error page.")
        return 0
    try:
        book = pd.ExcelFile(source)
        frames = []
        for sheet in book.sheet_names:
            try:
                frame = pd.read_excel(source, sheet_name=sheet, dtype=str).fillna("")
            except Exception as exc:
                print(f"[warning] NAMASTE sheet {sheet!r} could not be read: {exc}")
                continue
            if frame.empty:
                continue
            frame.columns = [clean_text(c) for c in frame.columns]
            frame["source_sheet"] = sheet
            frames.append(frame)
        if not frames:
            print("[error] NAMASTE workbook contained no readable non-empty sheets")
            return 0
        combined = pd.concat(frames, ignore_index=True, sort=False).fillna("")
        # Keep official column labels and all rows; do not reinterpret codes or definitions.
        target = OUT / "namaste_ayurveda_terminology.csv"
        combined.to_csv(target, index=False, encoding="utf-8-sig")
        print(f"[prepared] {target.relative_to(ROOT)}: {len(combined)} rows across {len(frames)} non-empty sheets")
        print(f"          columns: {', '.join(map(str, combined.columns[:12]))}")
        return len(combined)
    except Exception as exc:
        print(f"[error] Could not prepare NAMASTE workbook: {exc}")
        return 0


def locate_imppat_files():
    # Only files explicitly named as IMPPAT sources count. Previously this accidentally
    # classified the NAMASTE workbook as an IMPPAT candidate.
    candidates=[]
    for p in RAW.iterdir():
        if p.is_file() and p.suffix.lower() in {".csv",".tsv",".txt",".xlsx",".xls",".zip"} and p.name.lower().startswith("imppat_"):
            candidates.append(p)
    return candidates


def main():
    print("Preparing local research indexes from source files; source data is not edited or redistributed.\n")
    n1=prepare_columbia()
    n2=prepare_who_chunks()
    n3=prepare_namaste()
    imppat=locate_imppat_files()
    if not imppat:
        print("[missing] No IMPPAT source files found. Download the official 'Plant - Therapeutic use Association' table and 'Information on Medicinal Plants' table.")
    else:
        print("[found] IMPPAT-named source files (not necessarily sufficient for plant-use retrieval):")
        for p in imppat: print(f"  - {p.name} ({p.stat().st_size:,} bytes)")
        # The therapeutic-use association file is required for plant/use retrieval.
        use_files=[p for p in imppat if "therapeutic_use" in p.name.lower() or "therapeuticuse" in p.name.lower()]
        if not use_files:
            print("[missing] IMPPAT Plant - Therapeutic use Association table. Plant info alone is not enough to search plant/use associations.")
        else:
            print("The app will inspect the IMPPAT source tables for plant/use columns; source files are not rewritten.")
    print(f"\nPreparation summary: Columbia rows={n1}; WHO text chunks={n2}; NAMASTE terminology rows={n3}; IMPPAT-named source files={len(imppat)}")
    missing=[]
    if not n1: missing.append("Columbia")
    if not n2: missing.append("WHO PDF/text chunks")
    if not n3: missing.append("NAMASTE")
    if not any("therapeutic_use" in p.name.lower() or "therapeuticuse" in p.name.lower() for p in imppat): missing.append("IMPPAT plant-use association table")
    if missing:
        print("\n[not ready] Missing/incomplete sources: " + ", ".join(missing))
        print("See docs/DATA_SOURCES.md for official links and manual download filenames.")
    else:
        print("\n[ready] All four source layers have local files. Check app Dataset readiness for column recognition.")

if __name__ == "__main__":
    main()
