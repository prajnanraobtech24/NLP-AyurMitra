from __future__ import annotations

import json
import re
from functools import lru_cache  # ADDED FOR CACHING
from pathlib import Path
from typing import Iterable

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"


def normalize(text: str) -> str:
    text = str(text or "").lower()
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=1)  # ADDED FOR CACHING
def load_columbia() -> pd.DataFrame:
    path = PROCESSED / "columbia_disease_symptom.csv"

    if not path.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(path).fillna("")
        required = {"disease", "symptom"}

        if not required.issubset(
            {str(column).lower() for column in df.columns}
        ):
            return pd.DataFrame()

        rename = {
            column: str(column).lower()
            for column in df.columns
        }

        return df.rename(columns=rename)

    except Exception:
        return pd.DataFrame()


def score_conditions(
    user_text: str,
    df: pd.DataFrame,
    top_k: int = 8,
) -> list[dict]:
    """
    Rank source-listed conditions using symptom associations.

    This is an explainable text-matching heuristic, not a trained
    classifier, a clinical diagnosis, or a probability estimate.
    """
    query = normalize(user_text)
    
    if not query or df.empty or "disease" not in df.columns or "symptom" not in df.columns or top_k <= 0:
        return []

    # 1. Remove stop words so "fever and cough" becomes {"fever", "cough"}
    stop_words = {"and", "or", "with", "the", "a", "an", "in", "of", "for", "to", "is", "are"}
    query_tokens = {token for token in query.split() if token not in stop_words}

    if not query_tokens:
        return []

    candidates = []
    # 2. Find matching symptoms
    for _, row in df.iterrows():
        symptom = str(row.get("symptom", "")).strip()
        symptom_norm = normalize(symptom)
        
        if not symptom_norm:
            continue
            
        symptom_tokens = set(symptom_norm.split())
        
        # Check if ANY meaningful token matches
        matched_tokens = query_tokens.intersection(symptom_tokens)
        if not matched_tokens:
            continue

        candidates.append({
            "disease": str(row.get("disease", "Unknown")).strip() or "Unknown",
            "symptom": symptom,
            "symptom_norm": symptom_norm,
            "symptom_tokens": symptom_tokens,
            "matched_tokens": matched_tokens, # Track what actually matched for XAI
            "source_disease_count": str(row.get("disease_count_in_source", "")),
            "source_code": str(row.get("disease_code", "")),
        })

    if not candidates:
        return []

    # 3. Group by disease and deduplicate
    grouped = {}
    for item in candidates:
        disease = item["disease"]
        symptom = item["symptom"]
        
        if disease not in grouped:
            grouped[disease] = {
                "condition": disease,
                "matched_symptoms": set(),
                "_matched_query_tokens": set(),
                "source_disease_count": item["source_disease_count"],
                "source_code": item["source_code"],
            }
            
        grouped[disease]["matched_symptoms"].add(symptom)
        grouped[disease]["_matched_query_tokens"].update(item["matched_tokens"])

    results = []
    for disease, result in grouped.items():
        matched_tokens = result.pop("_matched_query_tokens")
        symptoms_list = sorted(list(result["matched_symptoms"]), key=str.lower)
        
        # Calculate coverage: How much of the user's query did this disease cover?
        token_coverage = len(matched_tokens) / len(query_tokens) if query_tokens else 0.0
        
        # Better scoring. Rewards diseases that match multiple symptoms
        score = (5.0 * token_coverage) + (1.5 * len(symptoms_list))

        result["matched_symptoms"] = symptoms_list
        result["score"] = round(score, 3)
        result["matched_query_token_count"] = len(matched_tokens)
        result["query_token_count"] = len(query_tokens)
        result["evidence"] = (
            "Source-listed disease-symptom associations. "
            "Score is a rule-based text-matching rank, not a probability."
        )
        results.append(result)

    # Sort by highest score, then by number of matched symptoms
    return sorted(results, key=lambda x: (-x["score"], -len(x["matched_symptoms"]), x["condition"].lower()))[:top_k]


@lru_cache(maxsize=1)  # ADDED FOR CACHING
def load_namaste_terms() -> pd.DataFrame:
    """Load the locally processed NAMASTE terminology workbook."""
    path = PROCESSED / "namaste_ayurveda_terminology.csv"

    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return pd.DataFrame()


def search_namaste_terms(
    query: str,
    df: pd.DataFrame,
    top_k: int = 8,
) -> list[dict]:
    """Search NAMASTE terminology fields, not diagnostic predictions."""
    query = normalize(query)

    if not query or df.empty or top_k <= 0:
        return []

    searchable_cols = [
        column
        for column in df.columns
        if any(
            key in normalize(column)
            for key in (
                "word",
                "definition",
                "term",
                "code",
                "reference",
                "parent",
            )
        )
    ]

    if not searchable_cols:
        searchable_cols = list(df.columns)

    corpus = (
        df[searchable_cols]
        .astype(str)
        .agg(" ".join, axis=1)
        .map(normalize)
        .tolist()
    )

    try:
        vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_features=30000,
        )

        matrix = vectorizer.fit_transform(corpus + [query])

        sims = cosine_similarity(
            matrix[-1], matrix[:-1]
        ).ravel()

        ids = sims.argsort()[::-1]
        out = []

        for idx in ids:
            if sims[idx] <= 0:
                continue

            row = df.iloc[int(idx)].to_dict()
            row["similarity"] = round(float(sims[idx]), 4)
            row["source"] = (
                "NAMASTE Portal — Standardized Ayurveda Terminologies"
            )
            row["source_url"] = (
                "https://namaste.ayush.gov.in/sat_Ayurveda"
            )

            out.append(row)

            if len(out) >= top_k:
                break

        return out

    except ValueError:
        return []


@lru_cache(maxsize=1)  # ADDED FOR CACHING
def load_who_chunks() -> list[dict]:
    path = PROCESSED / "who_ayurveda_chunks.jsonl"

    if not path.exists():
        return []

    chunks = []

    with path.open(encoding="utf-8") as file:
        for line in file:
            try:
                chunks.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return chunks


def search_text_chunks(
    query: str,
    chunks: list[dict],
    top_k: int = 5,
) -> list[dict]:
    if not query.strip() or not chunks or top_k <= 0:
        return []

    texts = [
        str(chunk.get("text", ""))
        for chunk in chunks
    ]

    try:
        vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_features=40000,
        )

        matrix = vectorizer.fit_transform(texts + [query])

        sims = cosine_similarity(
            matrix[-1], matrix[:-1]
        ).ravel()

        ids = sims.argsort()[::-1]

        return [
            {
                **chunks[int(idx)],
                "similarity": round(float(sims[idx]), 4),
            }
            for idx in ids[:top_k]
            if sims[idx] > 0
        ]

    except ValueError:
        return []


def _read_delimited_table(
    source,
    *,
    filename: str = "",
) -> pd.DataFrame:
    """Read CSV/TSV exports, including TSV files with a .csv suffix."""
    try:
        sample = (
            source.read(8192)
            if hasattr(source, "read")
            else Path(source).read_bytes()[:8192]
        )

        if isinstance(sample, bytes):
            sample_text = sample.decode(
                "utf-8-sig", errors="replace"
            )
        else:
            sample_text = str(sample)

        first_line = (
            sample_text.splitlines()[0]
            if sample_text.splitlines()
            else ""
        )

        delimiter = (
            "\t"
            if first_line.count("\t") > first_line.count(",")
            else ","
        )

        if hasattr(source, "seek"):
            source.seek(0)

        return pd.read_csv(
            source,
            sep=delimiter,
            dtype=str,
        ).fillna("")

    except Exception:
        return pd.DataFrame()


def _read_table(path: Path) -> pd.DataFrame:
    try:
        suffix = path.suffix.lower()

        if suffix in {".xlsx", ".xls"}:
            return pd.read_excel(
                path, dtype=str
            ).fillna("")

        if suffix == ".zip":
            import zipfile

            with zipfile.ZipFile(path) as archive:
                members = [
                    name
                    for name in archive.namelist()
                    if name.lower().endswith(
                        (".csv", ".tsv", ".xlsx", ".xls")
                    )
                    and not name.startswith("__MACOSX/")
                ]

                if not members:
                    return pd.DataFrame()

                members.sort(
                    key=lambda name: (
                        not any(
                            key in name.lower()
                            for key in (
                                "therapeutic",
                                "plant_info",
                                "plant-use",
                            )
                        ),
                        name.lower(),
                    )
                )

                member = members[0]

                with archive.open(member) as file:
                    if member.lower().endswith(
                        (".xlsx", ".xls")
                    ):
                        return pd.read_excel(
                            file, dtype=str
                        ).fillna("")

                    return _read_delimited_table(
                        file, filename=member
                    )

        return _read_delimited_table(
            path, filename=path.name
        )

    except Exception:
        return pd.DataFrame()


def load_imppat_tables() -> list[tuple[str, pd.DataFrame]]:
    tables = []

    for path in RAW.iterdir() if RAW.exists() else []:
        if (
            not path.is_file()
            or path.suffix.lower()
            not in {
                ".csv",
                ".tsv",
                ".txt",
                ".xlsx",
                ".xls",
                ".zip",
            }
        ):
            continue

        if not path.name.lower().startswith("imppat_"):
            continue

        df = _read_table(path)

        if not df.empty:
            tables.append((path.name, df))

    return tables


def _find_col(
    columns: Iterable[str],
    candidates: list[str],
) -> str | None:
    normalized = {
        column: normalize(column).replace(" ", "")
        for column in columns
    }

    for candidate in candidates:
        needle = normalize(candidate).replace(" ", "")

        for original, norm in normalized.items():
            if needle == norm:
                return original

    for candidate in candidates:
        needle = normalize(candidate).replace(" ", "")

        for original, norm in normalized.items():
            if needle in norm or norm in needle:
                return original

    return None


def find_imppat_use_tables(
    tables: list[tuple[str, pd.DataFrame]],
) -> list[dict]:
    """Adapt IMPPAT plant-part-use rows, including common-name aliases."""
    results = []

    plant_candidates = [
        "indian medicinal plant",
        "plant name",
        "plant",
        "scientific name",
        "medicinal plant",
        "species",
        "plant name scientific",
    ]

    use_candidates = [
        "therapeutic use",
        "therapeutic uses",
        "use",
        "therapeutic use name",
        "indication",
        "therapeutic indication",
    ]

    part_candidates = ["plant part", "plant parts", "part"]

    reference_candidates = [
        "references",
        "reference",
        "literature references",
        "source references",
    ]

    common_candidates = [
        "common name",
        "common names",
        "synonymous names",
        "synonyms",
        "vernacular name",
        "vernacular names",
    ]

    aliases_by_plant: dict[str, set[str]] = {}

    for filename, df in tables:
        plant_col = _find_col(df.columns, plant_candidates)

        common_cols = [
            column
            for column in df.columns
            if any(
                _find_col([column], [candidate]) == column
                for candidate in common_candidates
            )
        ]

        if not plant_col or not common_cols:
            continue

        for _, row in df.iterrows():
            plant = str(row.get(plant_col, "")).strip()

            if not plant:
                continue

            aliases = aliases_by_plant.setdefault(
                normalize(plant), set()
            )

            for column in common_cols:
                value = str(row.get(column, "")).strip()

                if value:
                    aliases.update(
                        alias.strip()
                        for alias in re.split(r"[,;|]", value)
                        if alias.strip()
                    )

    for filename, df in tables:
        plant_col = _find_col(df.columns, plant_candidates)
        use_col = _find_col(df.columns, use_candidates)
        part_col = _find_col(df.columns, part_candidates)
        ref_col = _find_col(df.columns, reference_candidates)

        if not plant_col or not use_col:
            continue

        for _, row in df.iterrows():
            plant = str(row.get(plant_col, "")).strip()
            use = str(row.get(use_col, "")).strip()

            part = (
                str(row.get(part_col, "")).strip()
                if part_col
                else ""
            )

            references = (
                str(row.get(ref_col, "")).strip()
                if ref_col
                else ""
            )

            if plant and use:
                results.append(
                    {
                        "plant": plant,
                        "plant_aliases": sorted(
                            aliases_by_plant.get(
                                normalize(plant), set()
                            )
                        ),
                        "plant_part": part,
                        "therapeutic_use": use,
                        "references": references,
                        "source_file": filename,
                        "source": "IMPPAT 2.0",
                        "source_url": "https://cb.imsc.res.in/imppat/",
                    }
                )

    return results


def search_imppat_uses(
    query: str,
    tables: list[tuple[str, pd.DataFrame]],
    top_k: int = 8,
) -> list[dict]:
    query = normalize(query)

    if not query or top_k <= 0:
        return []

    rows = find_imppat_use_tables(tables)

    if not rows:
        return []

    corpus = [
        normalize(
            row["therapeutic_use"]
            + " "
            + row["plant"]
            + " "
            + " ".join(row.get("plant_aliases", []))
            + " "
            + row["plant_part"]
        )
        for row in rows
    ]

    try:
        vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_features=30000,
        )

        matrix = vectorizer.fit_transform(corpus + [query])

        sims = cosine_similarity(
            matrix[-1], matrix[:-1]
        ).ravel()

        ids = sims.argsort()[::-1]
        out = []

        for idx in ids:
            if sims[idx] <= 0:
                continue

            out.append(
                {
                    **rows[int(idx)],
                    "similarity": round(float(sims[idx]), 4),
                    "note": (
                        "Source-listed plant/use association only; "
                        "not an individual recommendation or proof "
                        "of clinical efficacy."
                    ),
                }
            )

            if len(out) >= top_k:
                break

        return out

    except ValueError:
        return []


def build_imppat_graph(
    tables: list[tuple[str, pd.DataFrame]],
):
    """Build a bipartite graph of plants and therapeutic-use associations."""
    import networkx as nx

    graph = nx.Graph()

    for row in find_imppat_use_tables(tables):
        plant = row["plant"].strip()
        use = row["therapeutic_use"].strip()

        if not plant or not use:
            continue

        plant_node = "plant::" + plant
        use_node = "use::" + use

        graph.add_node(
            plant_node,
            label=plant,
            kind="plant",
            source=row["source_file"],
        )

        graph.add_node(
            use_node,
            label=use,
            kind="therapeutic_use",
            source=row["source_file"],
        )

        graph.add_edge(
            plant_node,
            use_node,
            plant_part=row.get("plant_part", ""),
            source=row["source_file"],
        )

    return graph


def dataset_status() -> dict:
    """
    Report dataset readiness and distinguish draft evidence
    from records marked as human-reviewed.
    """
    who_ready = (
        bool(load_who_chunks())
        and any(
            (RAW / name).is_file()
            and (RAW / name).stat().st_size > 100_000
            for name in (
                "who_ayurveda_terminologies.pdf",
                "WHO.pdf",
            )
        )
    )

    columbia_ready = not load_columbia().empty

    namaste_ready = (
        not load_namaste_terms().empty
        and any(
            (RAW / name).is_file()
            for name in (
                "namaste_ayurveda_sat_combined.xlsx",
                "ayu_sat_table_combined.xlsx",
            )
        )
    )

    imppat_ready = bool(
        find_imppat_use_tables(load_imppat_tables())
    )

    # AYUSH evidence register
    ayush_path = PROCESSED / "ayush_evidence_register.csv"
    ayush_ready = False
    ayush_reviewed_ready = False

    if ayush_path.is_file():
        try:
            ayush_df = pd.read_csv(ayush_path).fillna("")

            required_columns = {
                "record_id",
                "title",
                "authors",
                "year",
                "study_design",
                "claim",
                "limitations",
                "source_portal_url",
                "verified_by",
            }

            columns_present = required_columns.issubset(
                set(ayush_df.columns)
            )

            if columns_present and not ayush_df.empty:
                usable_record = (
                    ayush_df["record_id"].astype(str).str.strip().ne("")
                    & ayush_df["title"].astype(str).str.strip().ne("")
                    & ayush_df["claim"].astype(str).str.strip().ne("")
                    & ayush_df["source_portal_url"]
                    .astype(str)
                    .str.strip()
                    .ne("")
                )

                ayush_ready = bool(usable_record.any())

                reviewer_info = (
                    ayush_df["verified_by"].astype(str).str.strip()
                )

                review_is_pending = reviewer_info.str.contains(
                    r"\b(?:pending|draft|not verified|unverified)\b",
                    case=False,
                    regex=True,
                )

                # This checks metadata only; it cannot independently
                # establish that human review actually occurred.
                ayush_reviewed_ready = bool(
                    (
                        usable_record
                        & reviewer_info.ne("")
                        & ~review_is_pending
                    ).any()
                )

        except (OSError, ValueError, pd.errors.ParserError):
            ayush_ready = False
            ayush_reviewed_ready = False

    return {
        "WHO PDF and extracted terminology chunks": who_ready,
        "Columbia disease-symptom association table": columbia_ready,
        "NAMASTE standardized terminology workbook": namaste_ready,
        "IMPPAT plant-use association table": imppat_ready,
        "AYUSH Research Portal evidence register (file and schema ready)": (
            ayush_ready
        ),
        "AYUSH register contains records marked as human-reviewed": (
            ayush_reviewed_ready
        ),
    }