"""Audit source-file integrity, prepared schemas, counts, and missing dataset actions."""
from __future__ import annotations
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
sys.path.insert(0, str(ROOT))
from app.core import (load_columbia, load_who_chunks, load_namaste_terms,
                      load_imppat_tables, find_imppat_use_tables, dataset_status)

SOURCE_FILES = {
    "WHO": ["WHO.pdf", "who_ayurveda_terminologies.pdf"],
    "NAMASTE": ["namaste_ayurveda_sat_combined.xlsx", "ayu_sat_table_combined.xlsx"],
    "Columbia": ["columbia_disease_symptom_source.html"],
}

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def raw_file_records() -> list[dict]:
    records=[]
    for path in sorted(RAW.iterdir()) if RAW.exists() else []:
        if not path.is_file() or path.name == ".gitkeep":
            continue
        records.append({"file": str(path.relative_to(ROOT)).replace("\\", "/"),
                        "bytes": path.stat().st_size, "sha256": sha256(path)})
    return records

def main() -> int:
    status = dataset_status()
    who = load_who_chunks()
    col = load_columbia()
    nam = load_namaste_terms()
    tables = load_imppat_tables()
    use_rows = find_imppat_use_tables(tables)
    source_records = {
        "WHO": {"ready": status.get("WHO PDF and extracted terminology chunks", False),
                "raw_pdf_count": sum(1 for n in SOURCE_FILES["WHO"] if (RAW/n).is_file()),
                "prepared_chunks": len(who), "pages_represented": len({r.get("page") for r in who if r.get("page") is not None}),
                "purpose": "Terminology/document retrieval; not disease-label training data."},
        "NAMASTE": {"ready": status.get("NAMASTE standardized terminology workbook", False),
                    "rows": len(nam), "columns": list(nam.columns),
                    "sheets": int(nam["source_sheet"].nunique()) if not nam.empty and "source_sheet" in nam else 0,
                    "purpose": "Official Ayurveda terminology/code/definition lookup."},
        "IMPPAT": {"ready": status.get("IMPPAT plant-use association table", False),
                   "files": [{"name": n, "rows": len(df), "columns": list(df.columns)} for n,df in tables],
                   "usable_plant_use_associations": len(use_rows),
                   "purpose": "Source-listed plant-part/use associations; not personalized clinical recommendations."},
        "Columbia": {"ready": status.get("Columbia disease-symptom association table", False),
                     "rows": len(col), "distinct_diseases": int(col["disease"].nunique()) if not col.empty and "disease" in col else 0,
                     "columns": list(col.columns),
                     "purpose": "General disease/symptom association ranking; not Ayurveda-specific and not a validated classifier."},
        "AYUSH Research Portal": {"ready": status.get("AYUSH Research Portal manually reviewed evidence register", False),
                                  "purpose": "Only manually reviewed, cited records are indexed; portal is not assumed to provide a bulk dataset."}
    }
    optional_names = {"AYUSH Research Portal"}
    missing = [name for name, record in source_records.items() if not record.get("ready")]
    missing_required = [name for name in missing if name not in optional_names]
    missing_optional = [name for name in missing if name in optional_names]
    report = {
        "project": "AyurMitra",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_status": status,
        "sources": source_records,
        "raw_files": raw_file_records(),
        "missing_sources": missing,
        "missing_required_sources": missing_required,
        "missing_optional_sources": missing_optional,
        "next_actions": {
            "NAMASTE": "Download SAT-COMBINED from https://namaste.ayush.gov.in/sat_Ayurveda if absent; rerun downloader and preparation.",
            "IMPPAT": "Download the official Plant - Therapeutic use Association and Information on Medicinal Plants tables from https://cb.imsc.res.in/imppat/download if absent; retain original file formats and prefix filenames with imppat_.",
            "Columbia": "Retry official source download from https://impact.dbmi.columbia.edu/~friedma/Projects/DiseaseSymptomKB/index.html; if unavailable, do not substitute an unlicensed mirror without project approval.",
            "AYUSH Research Portal": "Add only manually reviewed citations/claims to the evidence register; do not scrape or invent records."
        },
        "integrity_note": "File hashes are recorded for reproducibility. Missing datasets are not fabricated. File existence alone does not imply clinical validity."
    }
    out = PROCESSED / "dataset_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nSaved: {out.relative_to(ROOT)}")
    return 0 if not missing_required else 2

if __name__ == "__main__":
    raise SystemExit(main())
