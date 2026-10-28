"""Application orchestration: language handling, evidence retrieval, and grounded answers."""
from __future__ import annotations

import re
from collections import defaultdict
from functools import lru_cache
from typing import Any

import pandas as pd

from app.core import (
    PROCESSED,
    canonical_symptom_terms,
    dataset_status,
    find_imppat_use_tables,
    load_columbia,
    load_imppat_tables,
    load_namaste_terms,
    load_who_chunks,
    normalize as normalize_term,
    score_conditions,
)
from app.language import detect_language, translator
from app.retrieval import correct_query_spelling, hybrid_search
from app.rag import generate_grounded_answer, translate_answer_with_ollama


ENGLISH_MNPUT = "English or romanized/code-mixed Latin input"

SOURCE_CATALOG = {
    "WHO Ayurveda terminology": "https://www.who.int/publications/i/item/9789240064935",
    "NAMASTE Standardized Ayurveda Terminologies": "https://namaste.ayush.gov.in/sat_Ayurveda",
    "IMPPAT 3.0": "https://cb.imsc.res.in/imppat/",
    "Columbia Diseaseâ€“Symptom Knowledge Database": "https://people.dbmi.columbia.edu/~friedma/Projects/DiseaseSymptomKB/index.html",
    "AYUSH Research Portal": "https://arp.ayush.gov.in/",
}

CATEGORY_LABELS = {
    "general": "General Ayurveda",
    "herbs": "Ayurvedic herbs",
    "disease": "Symptoms & conditions",
}

OUTPUT_LANGUAGES = {
    "english": ("English", "eng_Latn"),
    "hindi": ("Hindi", "hin_Deva"),
    "kannada": ("Kannada", "kan_Knda"),
    "tamil": ("Tamil", "tam_Taml"),
    "telugu": ("Telugu", "tel_Telu"),
}


def _source(name: str, url: str, detail: str = "") -> dict:
    return {"name": name, "url": url, "detail": detail}


def _normalize_text(value: Any) -> str:
    """Normalize text for case-insensitive exact/phrase matching."""
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _protect_terms(text: str, terms_df) -> tuple[str, dict[str, str]]:
    """Protect exact NAMASTE Latin-script terms while a query is translated."""
    if terms_df is None or terms_df.empty:
        return text, {}

    candidates = []
    for col in terms_df.columns:
        if any(k in str(col).lower() for k in ("word", "term", "name", "english")):
            candidates.extend(
                str(value).strip()
                for value in terms_df[col].dropna().tolist()
                if len(str(value).strip()) >= 3
            )

    replacements: dict[str, str] = {}
    result = text
    for term in sorted(set(candidates), key=len, reverse=True)[:5000]:
        if not re.search(r"[A-Za-z]", term):
            continue
        pattern = re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.M)
        if pattern.search(result):
            key = f"AYURMITRATERM{len(replacements)}X"
            result = pattern.sub(key, result)
            replacements[key] = term
    return result, replacements


def _restore_terms(text: str, replacements: dict[str, str]) -> str:
    for key, term in replacements.items():
        text = text.replace(key, term)
    return text


@lru_cache(maxsize=3)
def _flatten_evidence(category: str | None = None) -> list[dict]:
    """Load only the selected source category and cache its evidence records."""
    records: list[dict] = []

    for chunk in (load_who_chunks() if category != "herbs" else []):
        page = chunk.get("page", "?")
        records.append({
            "id": f"WHO-P{page}-C{chunk.get('chunk_id', '?')}",
            "source_name": "WHO International Standard Terminologies on Ayurveda",
            "source_url": chunk.get("source_url") or SOURCE_CATALOG["WHO Ayurveda terminology"],
            "source_detail": f"Page {page}",
            "title": f"WHO Ayurveda terminology - page {page}",
            "text": str(chunk.get("text", "")),
            "type": "terminology",
            "page": page,
        })

    namaste = load_namaste_terms() if category != "herbs" else pd.DataFrame()
    if namaste is not None and not namaste.empty:
        for idx, row in namaste.iterrows():
            row_dict = row.to_dict()
            parts = [
                f"{key}: {value}"
                for key, value in row_dict.items()
                if str(value).strip() and str(key) != "source_sheet"
            ]
            title = next(
                (
                    str(value)
                    for key, value in row.items()
                    if any(token in str(key).lower() for token in ("word", "term", "name"))
                    and str(value).strip()
                ),
                "NAMASTE terminology record",
            )
            records.append({
                "id": f"NAMASTE-{idx + 1}",
                "source_name": "NAMASTE Standardized Ayurveda Terminologies",
                "source_url": SOURCE_CATALOG["NAMASTE Standardized Ayurveda Terminologies"],
                "source_detail": str(row.get("source_sheet", "")),
                "title": title,
                "text": "; ".join(parts),
                "type": "terminology",
            })

    # Do not parse and expand the 94k-row plant table for general Ayurveda queries.
    tables = load_imppat_tables() if category in {None, "herbs"} else []
    for idx, row in enumerate(find_imppat_use_tables(tables)):
        aliases = row.get("plant_aliases", [])
        if isinstance(aliases, str):
            aliases_list = [aliases] if aliases.strip() else []
        elif isinstance(aliases, (list, tuple, set)):
            aliases_list = [
                str(alias).strip() for alias in aliases if str(alias).strip()
            ]
        else:
            aliases_list = []

        plant = str(row.get("plant", "") or "")
        therapeutic_use = str(row.get("therapeutic_use", "") or "")
        plant_part = str(row.get("plant_part", "") or "")
        references = str(row.get("references", "") or "")
        text = (
            f"Plant: {plant}; common names and synonyms: {', '.join(aliases_list)}; "
            f"therapeutic use: {therapeutic_use}; plant part: {plant_part}; "
            f"references: {references}"
        )
        record = dict(row)
        record.update({
            "id": f"IMPPAT-{idx + 1}",
            "source_name": "IMPPAT 3.0",
            "source_url": row.get("source_url") or SOURCE_CATALOG["IMPPAT 3.0"],
            "source_detail": row.get("source_file", ""),
            "title": plant or "Medicinal plant record",
            "text": text,
            "type": "plant_use",
            "plant": plant,
            "plant_aliases": aliases_list,
            "therapeutic_use": therapeutic_use,
            "plant_part": plant_part,
            "references": references,
        })
        records.append(record)

    # Only rows with a usable claim are included. The current register uses "claim";
    # older versions of the schema may use "claim_to_use".
    ayush_path = PROCESSED / "ayush_evidence_register.csv"
    if ayush_path.exists():
        try:
            ayush = pd.read_csv(ayush_path).fillna("")
            for idx, row in ayush.iterrows():
                claim = str(
                    row.get("claim", row.get("claim_to_use", ""))
                ).strip()
                title = str(row.get("title", "")).strip()
                reviewer = str(row.get("verified_by", "")).strip()
                review_pending = re.search(
                    r"\b(?:pending|draft|not verified|unverified)\b",
                    reviewer,
                    flags=re.IGNORECASE,
                )
                if not claim or not title or not reviewer or review_pending:
                    continue

                url = (
                    str(row.get("source_portal_url", "")).strip()
                    or SOURCE_CATALOG["AYUSH Research Portal"]
                )
                text = (
                    f"Title: {title}; authors: {row.get('authors', '')}; "
                    f"year: {row.get('year', '')}; study design: {row.get('study_design', '')}; "
                    f"claim recorded in register: {claim}; limitations: {row.get('limitations', '')}"
                )
                records.append({
                    "id": str(row.get("record_id", "")).strip() or f"AYUSH-{idx + 1}",
                    "source_name": "AYUSH Research Portal â€” evidence register",
                    "source_url": url,
                    "source_detail": (
                        f"{row.get('authors', '')} ({row.get('year', '')}); "
                        f"review status: {row.get('verified_by', 'not specified')}"
                    ),
                    "title": title,
                    "text": text,
                    "type": "reviewed_literature",
                })
        except (OSError, ValueError, pd.errors.ParserError):
            # An optional malformed register must not stop core search.
            pass

    return records


@lru_cache(maxsize=3)
def _evidence_for(category: str) -> tuple[dict, ...]:
    """Keep stable category-specific record lists for retrieval index reuse."""
    all_records = _flatten_evidence(category)
    if category == "general":
        allowed = {"terminology", "reviewed_literature"}
    elif category == "herbs":
        allowed = {"plant_use"}
    else:
        allowed = set()
    return tuple(item for item in all_records if item.get("type") in allowed)


def _deduplicate_hits(hits: list[dict]) -> list[dict]:
    """Deduplicate exact source records, preserving separate use/part rows."""
    unique = []
    seen = set()
    for hit in hits:
        key = hit.get("id") or (
            hit.get("source_name"), hit.get("title"), hit.get("text")
        )
        if key not in seen:
            seen.add(key)
            unique.append(hit)
    return unique


def _plant_names(hit: dict) -> list[str]:
    names = [_normalize_text(hit.get("plant", hit.get("title", "")))]
    aliases = hit.get("plant_aliases", [])
    if isinstance(aliases, str):
        aliases = [aliases]
    if isinstance(aliases, (list, tuple, set)):
        names.extend(_normalize_text(alias) for alias in aliases if alias)
    return list(dict.fromkeys(name for name in names if name))


def _query_plant_matches(query: str, hit: dict) -> bool:
    """True when a full plant name or alias occurs as a phrase in the query."""
    normalized_query = f" {_normalize_text(query)} "
    return any(f" {name} " in normalized_query for name in _plant_names(hit))


def _mentioned_plant_hits(query: str) -> tuple[dict, ...]:
    """Find corpus plant names/aliases embedded in a natural-language question."""
    normalized_query = f" {_normalize_text(query)} "
    found = []
    for name, rows in _plant_lookup().items():
        if len(name) >= 4 and f" {name} " in normalized_query:
            found.extend(rows)
    return tuple(_deduplicate_hits(found))


@lru_cache(maxsize=1)
def _plant_lookup() -> dict[str, tuple[dict, ...]]:
    """Precompute exact plant and alias lookup instead of rescanning every use row."""
    lookup: dict[str, list[dict]] = defaultdict(list)
    for item in _evidence_for("herbs"):
        names = [item.get("plant", "")]
        aliases = item.get("plant_aliases", [])
        if isinstance(aliases, str):
            aliases = [aliases]
        names.extend(aliases)
        for name in names:
            key = _normalize_text(name)
            if key:
                lookup[key].append(item)
    return {key: tuple(rows) for key, rows in lookup.items()}


def _query_use_terms(query: str, hits: list[dict]) -> set[str]:
    """Remove plant names and common question words to isolate requested use terms."""
    terms = set(_normalize_text(query).split())
    stop_words = {
        "what", "is", "are", "the", "a", "an", "in", "of", "for", "to", "and",
        "does", "do", "mean", "tell", "me", "about", "how", "can", "i", "please",
        "explain", "use", "uses", "herb", "herbs", "plant", "plants", "ayurvedic",
        "ayurveda", "remedy", "remedies", "treatment", "treat", "with", "using",
        "which", "according", "dataset", "records", "record", "listed", "listing",
        "traditionally", "traditional", "therapeutic", "recorded", "provide", "mentioned",
        "part", "parts", "my", "should", "take", "effective", "safe", "safely",
        "used", "useful", "compare", "comparison", "versus", "vs",
        "leaf", "leaves", "root", "roots", "bark", "seed", "seeds", "fruit",
        "fruits", "flower", "flowers", "stem", "stems",
        "imppat", "database",
    }
    terms -= stop_words
    for hit in hits:
        for name in _plant_names(hit):
            terms -= set(name.split())
    return terms


def _rank_herb_hits(query: str, hits: list[dict]) -> list[dict]:
    """Order plant records by exact plant match and requested-use overlap."""
    use_terms = _query_use_terms(query, hits)
    query_norm = _normalize_text(query)
    ranked = []

    for index, hit in enumerate(hits):
        plant = _normalize_text(hit.get("plant", hit.get("title", "")))
        aliases = hit.get("plant_aliases", [])
        if isinstance(aliases, str):
            aliases = [aliases]
        alias_text = " ".join(_normalize_text(alias) for alias in aliases)
        use = _normalize_text(hit.get("therapeutic_use", ""))

        score = 0.0
        if _query_plant_matches(query, hit):
            score += 100.0
        use_tokens = set(use.split())
        score += 12.0 * len(use_tokens & use_terms)
        if use and use in query_norm:
            score += 20.0
        if plant and plant in query_norm:
            score += 5.0
        if any(token in alias_text.split() for token in use_terms):
            score += 1.0

        # This is an internal ordering score, not a retrieval similarity score.
        ranked.append((score, -index, hit))

    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in ranked]


def _group_herb_hits(hits: list[dict]) -> list[dict]:
    """Group IMPPAT rows by plant and preserve any genuine retrieval score."""
    groups: dict[str, dict] = {}

    for hit in hits:
        plant = str(
            hit.get("plant", hit.get("title", "Medicinal plant record"))
            or "Medicinal plant record"
        ).strip()
        key = _normalize_text(plant) or plant.lower()

        if key not in groups:
            aliases = hit.get("plant_aliases", [])
            if isinstance(aliases, str):
                aliases = [aliases] if aliases.strip() else []
            elif not isinstance(aliases, (list, tuple, set)):
                aliases = []

            group = {
                "id": f"IMPPAT-GROUP-{key.replace(' ', '-')}",
                "source_name": hit.get("source_name", "IMPPAT 3.0"),
                "source_url": hit.get("source_url") or SOURCE_CATALOG["IMPPAT 3.0"],
                "source_detail": "Grouped from IMPPAT 3.0 plant-use association records",
                "title": plant,
                "plant": plant,
                "plant_aliases": list(aliases),
                "type": "plant_use_group",
                "grouped_uses": [],
                "source_record_count": 0,
                "references": [],
            }
            # Only add the field if the input actually has a numeric score.
            # Exact plant-name matches intentionally bypass hybrid_search, so they
            # should not be assigned a fabricated score of zero.
            try:
                score = float(hit["retrieval_score"])
                if score == score:  # reject NaN
                    group["retrieval_score"] = score
            except (KeyError, TypeError, ValueError):
                pass
            groups[key] = group

        group = groups[key]
        group["source_record_count"] += 1

        # Preserve the best genuine score from any row in the group.
        try:
            score = float(hit["retrieval_score"])
            if score == score:  # reject NaN
                group["retrieval_score"] = max(
                    group.get("retrieval_score", score), score
                )
        except (KeyError, TypeError, ValueError):
            pass

        use = str(hit.get("therapeutic_use", "") or "").strip()
        part = str(hit.get("plant_part", "") or "").strip()
        references = str(hit.get("references", "") or "").strip()
        use_key = (_normalize_text(use), _normalize_text(part))

        if not any(
            (
                _normalize_text(item.get("use", "")),
                _normalize_text(item.get("plant_part", "")),
            ) == use_key
            for item in group["grouped_uses"]
        ):
            group["grouped_uses"].append({"use": use, "plant_part": part})

        if references and references not in group["references"]:
            group["references"].append(references)

    results = list(groups.values())
    for group in results:
        aliases = ", ".join(
            dict.fromkeys(str(alias) for alias in group["plant_aliases"] if alias)
        )
        by_use: dict[str, list[str]] = defaultdict(list)
        for item in group["grouped_uses"]:
            use = item["use"] or "use not specified"
            part = item["plant_part"] or "plant part not specified"
            if part not in by_use[use]:
                by_use[use].append(part)

        use_lines = [
            f"- {use}: {', '.join(parts)}"
            for use, parts in sorted(by_use.items(), key=lambda pair: pair[0].lower())
        ]
        group["text"] = (
            f"Plant: {group['plant']}; common names and synonyms: {aliases}; "
            "recorded IMPPAT therapeutic-use associations:\n" + "\n".join(use_lines)
        )
        group["summary"] = (
            f"{group['plant']} has {len(by_use)} distinct recorded therapeutic-use label(s) "
            f"across {group['source_record_count']} source record(s)."
        )

    return results


def _build_condition_hits(search_query: str) -> list[dict]:
    """Retrieve Columbia clinical associations separately from herb evidence."""
    conditions = score_conditions(search_query, load_columbia(), top_k=8)
    hits = []

    for condition in conditions:
        name = str(condition.get("condition", condition.get("disease", "Unknown condition")))
        matched_symptoms = condition.get("matched_symptoms", []) or []
        score = condition.get("score", 0)
        source_code = condition.get("source_code", "")
        hits.append({
            "id": "COLUMBIA-" + str(source_code or name),
            "source_name": "Columbia Diseaseâ€“Symptom Knowledge Database",
            "source_url": SOURCE_CATALOG["Columbia Diseaseâ€“Symptom Knowledge Database"],
            "source_detail": "General clinical disease-symptom association; not Ayurveda-specific",
            "title": name,
            "text": (
                f"Condition association record: {name}; matching symptoms: "
                f"{', '.join(matched_symptoms)}. Text-overlap score {score}; "
                "not a probability or validated diagnostic prediction."
            ),
            "type": "symptom_association",
            "retrieval_score": score,
            "matched_symptoms": matched_symptoms,
        })

    return _deduplicate_hits(hits)


def _herb_answer(query: str, hits: list[dict]) -> tuple[str, str, list[int]]:
    """Create a concise answer from grouped IMPPAT associations."""
    if not hits:
        return (
            "No matching plant-use record was found in the local IMPPAT evidence for this query. "
            "This does not establish that a plant has no traditional uses.",
            "no matching herb evidence found",
            [],
        )

    use_terms = _query_use_terms(query, hits)
    query_mentions_use = bool(use_terms)
    query_words = set(_normalize_text(query).split())
    part_aliases = {
        "leaf": {"leaf", "leaves"}, "root": {"root", "roots"},
        "bark": {"bark"}, "seed": {"seed", "seeds"},
        "fruit": {"fruit", "fruits"}, "flower": {"flower", "flowers"},
        "stem": {"stem", "stems"},
    }
    requested_parts = {
        part for part, aliases in part_aliases.items() if query_words & aliases
    }
    answer_parts: list[str] = []
    citations: list[int] = []

    for index, hit in enumerate(hits[:3], start=1):
        plant = hit.get("plant", hit.get("title", "the plant"))
        uses = hit.get("grouped_uses", [])

        if query_mentions_use or requested_parts:
            matched = []
            for item in uses:
                use_norm = _normalize_text(item.get("use", ""))
                use_tokens = set(use_norm.split())
                part_norm = _normalize_text(item.get("plant_part", ""))
                requested_part_matches = not requested_parts or any(
                    alias in part_norm
                    for requested in requested_parts
                    for alias in part_aliases[requested]
                )
                use_matches = not query_mentions_use or (
                    use_tokens & use_terms
                    or any(term in use_norm for term in use_terms)
                )
                if use_norm and requested_part_matches and use_matches:
                    matched.append(item)

            if not matched:
                continue

            by_use: dict[str, list[str]] = defaultdict(list)
            for item in matched:
                use = str(item.get("use") or "use not specified").strip()
                part = str(item.get("plant_part") or "").strip()
                if part and part not in by_use[use]:
                    by_use[use].append(part)

            details = []
            for use, parts in sorted(by_use.items(), key=lambda pair: pair[0].lower()):
                specific_parts = [
                    part for part in parts
                    if _normalize_text(part) not in {
                        "plant part not specified", "not specified", "unknown", "n a", "na"
                    }
                ]
                shown_parts = specific_parts or parts
                if shown_parts:
                    label = "part listed" if len(shown_parts) == 1 else "parts listed"
                    details.append(f"{use} ({label}: {', '.join(shown_parts)})")
                else:
                    details.append(use)

            if details:
                answer_parts.append(
                    f"IMPPAT records for {plant} list " + "; ".join(details) + f" [E{index}]"
                )
                citations.append(index)
        else:
            use_names = sorted(
                {
                    str(item.get("use") or "").strip()
                    for item in uses
                    if str(item.get("use") or "").strip()
                },
                key=str.lower,
            )
            parts = sorted({
                str(item.get("plant_part") or "").strip()
                for item in uses
                if str(item.get("plant_part") or "").strip()
            }, key=str.lower)
            if use_names:
                part_text = f" Recorded plant parts include {', '.join(parts[:5])}." if parts else ""
                answer_parts.append(
                    f"The local IMPPAT table contains {len(use_names)} therapeutic-use labels for "
                    f"{plant} [E{index}]. The table does not identify a primary use or establish "
                    f"that any listed association is effective or suitable for you.{part_text}"
                )
            else:
                answer_parts.append(
                    f"IMPPAT contains a plant-use record for {plant}, but no use labels were "
                    f"available in the retrieved record [E{index}]"
                )
            citations.append(index)

    if not answer_parts:
        return (
            "I found plant records, but none clearly matched the requested use in the local evidence. "
            "Open the evidence records to inspect their listed associations.",
            "grounded abstention",
            [],
        )

    answer = ". ".join(answer_parts).rstrip(". ")
    answer += (
        ". These are source-listed associations, not proof of clinical effectiveness, safety, "
        "or suitability for an individual."
    )
    return answer, "extractive grounded herb lookup", citations


def _translation_unavailable_response(
    query: str, category: str, language: dict, reason: str,
    answer_mode: str = "extractive",
    output_language: str = "auto",
) -> dict:
    target_name, _ = _output_language(language, output_language)
    generated = generate_grounded_answer(query, [], target_name, answer_mode)
    answer = generated["answer"]
    generated_mode = str(generated.get("answer_mode", ""))
    generated_in_target = generated_mode.startswith(("General AI answer", "Generative RAG"))
    if generated_in_target:
        answer = f"[AI-generated; not based on local records] {answer}"
    else:
        answer = (
            f"I detected {language['name']} input ({query}), but translation is unavailable and "
            "the AI could not generate a reliable answer. Please ask in English or try again "
            "after enabling the supported translation model."
        )
    answer_language = (
        target_name if target_name == "English" or _has_expected_script(answer, target_name)
        else f"English ({target_name} response unavailable)"
    )
    return {
        "query": query,
        "category": category,
        "category_label": CATEGORY_LABELS[category],
        "detected_language": language["name"],
        "language_detection": language,
        "translation_ready": False,
        "translation_note": "",
        "answer": answer,
        "answer_mode": generated_mode if generated_in_target else "grounded abstention",
        "answer_language": answer_language,
        "answer_citations": generated.get("citations", []) if generated_in_target else [],
        "summary": (
            "No local evidence search was run because input translation is unavailable. "
            "The answer is general AI output, not based on local records."
            if generated_in_target else
            "No local evidence search was run because input translation is unavailable."
        ),
        "sections": [],
        "sources": [],
        "dataset_status": dataset_status(),
        "limitations": [
            reason,
            "No local evidence was searched; a generated answer is general information and may be wrong." if generated_in_target else "The AI fallback did not return an answer.",
            "Enable the supported IndicTrans2 route for Hindi/Kannada as described in docs/MULTILINGUAL_SETUP.md.",
        ],
        "xai_data": [],
    }


def _answer_language(language: dict) -> str:
    """Choose a requested response language when the query itself is not translated."""
    name = str(language.get("name", ""))
    if name.startswith("Possible romanized Hindi"):
        return "Hindi"
    if name.startswith("Possible romanized Kannada"):
        return "Kannada"
    if name.startswith("Hindi"):
        return "Hindi"
    if name.startswith("Kannada"):
        return "Kannada"
    if name.startswith("Tamil"):
        return "Tamil"
    if name.startswith("Telugu"):
        return "Telugu"
    if name not in {ENGLISH_MNPUT, "English"} and not translator.enabled:
        return name
    return "English"


def _output_language(language: dict, preference: str = "auto") -> tuple[str, str]:
    """Resolve the requested answer language independently from the search language."""
    choice = str(preference or "auto").lower()
    if choice in OUTPUT_LANGUAGES:
        return OUTPUT_LANGUAGES[choice]
    name = str(language.get("name", ""))
    if name.startswith("Hindi") or name.startswith("Possible romanized Hindi"):
        return OUTPUT_LANGUAGES["hindi"]
    if name.startswith("Kannada") or name.startswith("Possible romanized Kannada"):
        return OUTPUT_LANGUAGES["kannada"]
    if name.startswith("Tamil"):
        return OUTPUT_LANGUAGES["tamil"]
    if name.startswith("Telugu"):
        return OUTPUT_LANGUAGES["telugu"]
    return OUTPUT_LANGUAGES["english"]


def _has_expected_script(text: str, language_name: str) -> bool:
    script_ranges = {
        "Hindi": r"\u0900-\u097f",
        "Kannada": r"\u0c80-\u0cff",
        "Tamil": r"\u0b80-\u0bff",
        "Telugu": r"\u0c00-\u0c7f",
    }
    script = script_ranges.get(language_name)
    return True if not script else len(re.findall(f"[{script}]", text)) >= 3


def _strip_translation_commentary(text: str) -> str:
    return re.sub(r"(?is)\s*\n+\s*(?:\(\s*)?translation\s*:\s*.*\Z", "", text).strip()


def _founder_question(query: str) -> bool:
    normalized = _normalize_text(query)
    asks_identity = re.search(r"\b(father|founder|originator)\b", normalized)
    mentions_ayurveda = re.search(r"\bayurved(?:a|ic)?\b", normalized)
    asks_history = re.search(r"\b(history|role|text|surgery|compare|difference|different)\b", normalized)
    names_historical_figure = re.search(r"\b(charaka|caraka|sushruta|dhanvantari)\b", normalized)
    return bool(
        (asks_identity and mentions_ayurveda)
        or (asks_history and (names_historical_figure or mentions_ayurveda))
    )


def _ayurveda_definition_question(query: str) -> bool:
    normalized = _normalize_text(query)
    return bool(
        re.search(r"\bayurved(?:a|aa)?\b", normalized)
        and (normalized == "ayurveda" or re.search(r"\b(mean|meaning|define|definition|origin)\b|what is", normalized))
    )


def _who_dosha_answer(query: str, evidence: tuple[dict, ...]) -> tuple[str, list[dict]] | None:
    normalized = _normalize_text(query)
    terms = [name for name in ("vata", "pitta", "kapha") if re.search(rf"\b{name}\b", normalized)]
    if not set(terms) == {"vata", "pitta", "kapha"} and not re.search(r"\b(?:three|3) doshas?\b", normalized):
        return None
    terms = ["vata", "pitta", "kapha"]
    definitions = []
    hits = []
    for term in terms:
        found = None
        for item in evidence:
            if not str(item.get("id", "")).startswith("WHO-"):
                continue
            text = str(item.get("text", ""))
            match = re.search(
                rf"\b{term},\s*do.{{0,3}}ha\s+(.{{8,220}}?)"
                r"(?=\s+(?:ITA-\d|(?:Vata|Pitta|Kapha)\s+is\b|One of the three|Subtype of)|$)",
                text,
                re.I,
            )
            if match:
                found = (item, re.sub(r"\s+", " ", match.group(1)).strip(" .;:-"))
                break
        if not found:
            return None
        item, description = found
        hits.append({**item, "retrieval_score": 1.0, "retrieval_method": "WHO dosha terminology row"})
        definitions.append(f"{term.title()} is described as {description.lower()} [E{len(hits)}]")
    return "In the WHO Ayurveda terminology, " + "; ".join(definitions) + ".", hits


def search_project(
    query: str,
    category: str = "general",
    answer_mode: str = "extractive",
    output_language: str = "auto",
) -> dict:
    original = (query or "").strip()
    if not original:
        raise ValueError("Please enter a question or search term.")
    if len(original) > 2000:
        raise ValueError("Please keep the question under 2,000 characters.")
    if category not in {"general", "herbs", "disease"}:
        raise ValueError("Choose General Ayurveda, Ayurvedic herbs, or Symptoms & conditions.")
    if output_language not in {"auto", *OUTPUT_LANGUAGES}:
        raise ValueError("Choose Auto, English, Hindi, Kannada, Tamil, or Telugu for the answer language.")

    lang = detect_language(original)
    target_language, target_language_code = _output_language(lang, output_language)
    search_query = original
    translation_note = ""
    terms = None
    protected, glossary = original, {}
    if lang["name"] != ENGLISH_MNPUT and not lang["name"].startswith("Possible romanized"):
        terms = load_namaste_terms()
        protected, glossary = _protect_terms(original, terms)

    if lang["name"].startswith("Possible romanized"):
        translation_note = (
            "Romanized language detection is heuristic. The query was searched as typed; "
            "translation is not guaranteed."
        )
    elif lang["name"] != ENGLISH_MNPUT:
        if not lang.get("code"):
            return _translation_unavailable_response(
                original,
                category,
                lang,
                "No translation route is configured for this detected script.",
                answer_mode,
                output_language,
            )
        try:
            search_query = translator.translate(
                protected, lang["code"], "eng_Latn"
            )
            search_query = _restore_terms(search_query, glossary)
            translation_note = (
                "Input was translated to English for retrieval; terminology placeholders "
                "were restored before searching."
            )
        except Exception as exc:
            return _translation_unavailable_response(
                original, category, lang, str(exc), answer_mode, output_language
            )

    xai_data = []
    generation_language = target_language

    if category in {"general", "herbs"}:
        spelling_records = _evidence_for(category)
        corrected_query = correct_query_spelling(search_query, spelling_records)
        if corrected_query != search_query:
            search_query = corrected_query
            correction_note = "Likely spelling correction applied for source search."
            translation_note = f"{translation_note} {correction_note}".strip()

    if category == "general":
        evidence = _evidence_for("general")
        hits = _deduplicate_hits(hybrid_search(search_query, evidence, top_k=8))[:8]
        if _founder_question(search_query):
            normalized_history_query = _normalize_text(search_query)
            if re.search(r"\bsurgery\b", normalized_history_query):
                answer = (
                    "The Ministry of AYUSH describes the Sushruta Samhita, attributed to Sushruta, "
                    "as a classical text focused on surgery. Its report also says Sushruta learned "
                    "from Dhanvantari [E1]."
                )
            elif "dhanvantari" in normalized_history_query:
                answer = (
                    "The Ministry of AYUSH report describes Dhanvantari as a teacher in the surgical "
                    "tradition: Sushruta learned from him, and the Sushruta Samhita is associated with "
                    "that teaching [E1]."
                )
            elif "charaka" in normalized_history_query or "caraka" in normalized_history_query:
                answer = (
                    "The Ministry of AYUSH report links Charaka with the Charaka Samhita, a foundational "
                    "Ayurveda text, and Sushruta with the Sushruta Samhita, a work focused on surgery [E1]."
                )
            else:
                answer = (
                    "The Ministry of AYUSH history summary cited here does not assign one person a single "
                    "‘father of Ayurveda’ title. It attributes the Charaka Samhita to Charaka and the "
                    "Sushruta Samhita to Sushruta, and describes Sushruta’s surgical tradition as drawing "
                    "on Dhanvantari’s teachings [E1]. So the answer depends on whether you mean the classical "
                    "text tradition, surgery, or the revered teacher figure."
                )
            hits = [{
                "id": "AYUSH-HISTORY-CHARAKA-SUSHRUTA-DHANVANTARI",
                "source_name": "Ministry of AYUSH Annual Report 2024–25",
                "source_url": "https://ayush.gov.in/resources/pdf/annualReport/Annual-Report24-25_English.pdf",
                "source_detail": "History of Ayurveda; Charaka Samhita, Sushruta Samhita, and Dhanvantari",
                "title": "Classical Ayurveda texts and historical figures",
                "text": answer,
                "type": "curated_historical_fact",
                "retrieval_score": 1.0,
                "retrieval_method": "curated factual query",
            }]
            answer_mode_setting = "Curated historical source answer"
            answer_citations = [1]
            rag = None
        elif dosha_answer := _who_dosha_answer(search_query, evidence):
            answer, hits = dosha_answer
            answer_mode_setting = "Extractive WHO terminology answer"
            answer_citations = list(range(1, len(hits) + 1))
            rag = None
        elif _ayurveda_definition_question(search_query):
            definition_hit = next((
                item for item in evidence
                if re.search(r"term_iast:\s*ā?yurvedaḥ?\s*;", str(item.get("text", "")), re.I)
                or set(normalize_term((re.search(r"term_iast:\s*([^;]+)", str(item.get("text", "")), re.I) or [None, ""])[1]).split())
                in ({"ayurvedah"}, {"ayurveda"})
            ), None)
            if definition_hit:
                text = str(definition_hit.get("text", ""))
                translation = re.search(r"w_trans:\s*([^;]+)", text, re.I)
                term = re.search(r"term_iast:\s*([^;]+)", text, re.I)
                answer = (
                    f"In the NAMASTE terminology, {term.group(1).strip()} means "
                    f'"{translation.group(1).strip().lower()}" [E1].'
                    if term and translation else
                    f"The NAMASTE terminology defines Ayurveda as ‘science of life’ [E1]."
                )
                if "origin" in _normalize_text(search_query):
                    answer += " This term record does not give a historical origin."
                hits = [{**definition_hit, "retrieval_score": 1.0, "retrieval_method": "exact NAMASTE term match"}]
                answer_mode_setting = "Extractive answer"
                answer_citations = [1]
            else:
                answer = "The local terminology record did not contain a direct Ayurveda definition."
                answer_mode_setting = "grounded abstention"
                answer_citations = []
            rag = None
        else:
            rag = "continue"
        plain_query = normalize_term(search_query)
        query_words = set(plain_query.split()) - {
            "what", "is", "are", "the", "a", "an", "in", "of", "for", "does",
            "do", "mean", "meaning", "tell", "me", "about", "please", "explain",
            "define", "ayurveda", "ayurvedic", "everyday", "plain", "normal",
            "differ", "difference", "between", "describe", "describes",
            "term", "terms", "how",
            "origin",
        }
        if not query_words and re.search(r"\bayurved", plain_query):
            query_words = {"ayurveda"}
        exact_terms = []
        for item in evidence if rag is not None else ():
            if item.get("type") != "terminology":
                continue
            term_match = re.search(r"(?:^|;)\s*term_iast:\s*([^;]+)", str(item.get("text", "")), re.I)
            if not term_match:
                continue
            term_words = set(normalize_term(term_match.group(1)).split())
            term_words_without_visarga = {
                token[:-1] if token.endswith("h") else token for token in term_words
            }
            if query_words and (
                query_words == term_words
                or query_words == term_words_without_visarga
                or (term_words and term_words.issubset(query_words))
                or (term_words_without_visarga and term_words_without_visarga.issubset(query_words))
            ):
                exact_terms.append({**item, "retrieval_score": 1.0, "retrieval_method": "exact NAMASTE term match"})
        for item in evidence if rag is not None else ():
            if item.get("type") != "terminology" or not str(item.get("id", "")).startswith("WHO-"):
                continue
            text = str(item.get("text", ""))
            if query_words and any(
                re.search(rf"\b{re.escape(term)}\s*,\s*do.{{0,3}}ha\b", text, re.I)
                for term in query_words
            ):
                exact_terms.append({**item, "retrieval_score": 1.0, "retrieval_method": "exact WHO concept match"})
        if exact_terms:
            exact_ids = {item.get("id") for item in exact_terms}
            hits = exact_terms + [item for item in hits if item.get("id") not in exact_ids]
            hits = hits[:8]
        if rag is not None:
            rag_evidence = [{**hit, "summary": hit.get("text", "")} for hit in hits]
            rag = generate_grounded_answer(search_query, rag_evidence, generation_language, answer_mode)
            answer = rag["answer"]
            answer_mode_setting = rag.get("answer_mode", "grounded RAG")
            answer_citations = rag.get("citations", [])

    elif category == "herbs":
        evidence = _evidence_for("herbs")

        # Plant/alias mentions inside a full question must outrank unrelated lexical hits.
        named_plant_hits = _mentioned_plant_hits(search_query)
        if named_plant_hits:
            candidate_hits = named_plant_hits
        else:
            candidate_hits = hybrid_search(search_query, evidence, top_k=80)

        candidate_hits = _deduplicate_hits(candidate_hits)
        ranked_hits = _rank_herb_hits(search_query, candidate_hits)
        hits = _group_herb_hits(ranked_hits)[:8]
        answer, answer_mode_setting, answer_citations = _herb_answer(search_query, hits)
        if answer_mode == "ollama":
            generated = generate_grounded_answer(search_query, hits, generation_language, "ollama")
            if str(generated.get("answer_mode", "")).startswith("Generative RAG"):
                answer, answer_mode_setting, answer_citations = (
                    generated["answer"], generated["answer_mode"], generated["citations"]
                )
        elif not answer_citations:
            generated = generate_grounded_answer(search_query, [], generation_language, "extractive")
            answer, answer_mode_setting, answer_citations = (
                generated["answer"], generated["answer_mode"], generated["citations"]
            )

    else:
        hits = _build_condition_hits(search_query)[:5]
        answer_hits = [
            hit for hit in hits if hit.get("type") == "symptom_association"
        ]
        if answer_hits:
            matched_symptoms = list(dict.fromkeys(
                symptom
                for hit in answer_hits
                for symptom in hit.get("matched_symptoms", [])
                if symptom
            ))
            source_wording = ", ".join(matched_symptoms[:5])
            concepts = canonical_symptom_terms(search_query)
            display_names = {
                "headache": "headache",
                "abdominal discomfort": "stomach pain or cramps",
                "chest pain": "chest pain",
                "back pain": "back pain",
            }
            symptom_text = ", ".join(
                display_names.get(concept, concept) for concept in concepts
            ) or search_query
            source_name = "Columbia disease-symptom database"
            evidence_hit = {
                "id": "COLUMBIA-SYMPTOM-MATCH",
                "source_name": source_name,
                "source_url": "https://impact.dbmi.columbia.edu/~friedma/Projects/DiseaseSymptomKB/index.html",
                "source_detail": "Matched source wording; association data only",
                "title": "Symptom wording match",
                "text": (
                    f"The query was interpreted as {symptom_text}. Matching source symptom labels: "
                    f"{source_wording}. These labels come from general hospital-record associations; "
                    "they do not identify a cause or treatment."
                ),
                "type": "symptom_association",
                "matched_symptoms": matched_symptoms,
            }
            # Keep noisy disease labels out of the user-facing results. The source link and
            # matched symptom wording remain visible as evidence for how retrieval worked.
            hits = [evidence_hit]
            xai_data = []
            answer = (
                f"I read your query as {symptom_text}. The local search matched the source wording "
                f"{source_wording} [E1]. This is a general hospital-record association, not a diagnosis "
                "or an explanation of what is causing your symptom, and the source is not Ayurveda-specific. "
                "The local Ayurveda references do not validate a remedy for this symptom, so I cannot "
                "recommend a herb or dose from these matches. If the pain is severe, sudden, or getting "
                "worse, seek medical care."
            )
            normalized_query = _normalize_text(search_query)
            query_words = set(normalized_query.split())
            if "chest pain" in normalized_query or {"chest", "pain"}.issubset(query_words):
                answer += (
                    " For severe, sudden, persistent chest pain, or pain with breathlessness, sweating, "
                    "fainting, or pain spreading to the arm or jaw, seek emergency care."
                )
            answer_mode_setting = "grounded clinical association lookup"
            answer_citations = [1]
            if answer_mode == "ollama":
                generated = generate_grounded_answer(
                    search_query, [evidence_hit], generation_language, "ollama"
                )
                if str(generated.get("answer_mode", "")).startswith("Generative RAG"):
                    answer, answer_mode_setting, answer_citations = (
                        generated["answer"], generated["answer_mode"], generated["citations"]
                    )
        else:
            generated = generate_grounded_answer(search_query, [], generation_language, answer_mode)
            answer, answer_mode_setting, answer_citations = (
                generated["answer"], generated["answer_mode"], generated["citations"]
            )

    answer_translation_status = target_language
    generated_in_target = str(answer_mode_setting).startswith(("General AI answer", "Generative RAG"))
    if target_language_code == "eng_Latn":
        answer_translation_status = "English"
    elif generated_in_target and _has_expected_script(answer, target_language):
        answer_translation_status = target_language
    elif translator.enabled:
        try:
            if terms is None:
                terms = load_namaste_terms()
            protected_answer, answer_glossary = _protect_terms(answer, terms)
            translated = translator.translate(
                protected_answer, "eng_Latn", target_language_code
            )
            answer = _restore_terms(translated, answer_glossary)
            answer_translation_status = target_language
        except Exception as exc:
            answer_translation_status = f"English ({target_language} translation failed)"
            translation_note = f"The answer could not be translated into {target_language}: {str(exc)[:80]}"
    else:
        try:
            if terms is None:
                terms = load_namaste_terms()
            protected_answer, answer_glossary = _protect_terms(answer, terms)
            translated = translate_answer_with_ollama(protected_answer, target_language)
        except Exception:
            translated = None
        if translated:
            answer = _restore_terms(translated, answer_glossary)
            answer_translation_status = target_language
        else:
            answer_translation_status = f"English ({target_language} translation unavailable)"
            translation_note = (
                f"The answer remains in English because translation to {target_language} was unavailable."
            )

    if target_language != "English":
        answer = _strip_translation_commentary(answer)

    sections = []
    sources = []
    grouped: dict[str, list[dict]] = {}

    for index, hit in enumerate(hits, start=1):
        name = hit.get("source_name", "Reference source")
        retrieval_score = hit.get("retrieval_score")
        if isinstance(retrieval_score, (int, float)) and retrieval_score == retrieval_score:
            detail = f"Evidence ID E{index} Â· retrieval score {retrieval_score:.3f}"
        elif hit.get("type") == "plant_use_group":
            detail = (
                f"Evidence ID E{index} Â· grouped from "
                f"{hit.get('source_record_count', 0)} IMPPAT source records; "
                "exact plant/alias match (no similarity score calculated)"
            )
        else:
            detail = f"Evidence ID E{index}"

        grouped.setdefault(name, []).append({
            "id": hit.get("id", f"E{index}"),
            "title": hit.get("title", "Source record"),
            "summary": str(hit.get("text", ""))[:1000],
            "detail": detail,
            "source": _source(
                name,
                hit.get("source_url") or SOURCE_CATALOG.get(
                    name, SOURCE_CATALOG["AYUSH Research Portal"]
                ),
                hit.get("source_detail", ""),
            ),
            "type": hit.get("type", "reference"),
        })
        source = _source(
            name,
            hit.get("source_url") or SOURCE_CATALOG.get(
                name, SOURCE_CATALOG["AYUSH Research Portal"]
            ),
            hit.get("source_detail", ""),
        )
        if not any(existing["name"] == name for existing in sources):
            sources.append(source)

    for name, items in grouped.items():
        sections.append({"title": name, "items": items})

    ready = dataset_status()
    limitations = [
        "AyurMitra is a research prototype, not a diagnostic system. A source association is not a probability or a personalized recommendation.",
        "IMPPAT lists plant/use associations; these do not establish safety, efficacy, suitability, or dosage for an individual.",
        "Columbia is a general clinical association dataset, not Ayurveda-specific. Missing local datasets cannot contribute evidence.",
    ]
    if translation_note:
        limitations.append(translation_note)
    if str(answer_mode_setting).startswith("General AI answer"):
        limitations.append(
            "The answer uses general local-model knowledge and is not supported by the displayed local records."
        )
    elif str(answer_mode_setting).startswith(("grounded abstention", "Grounded abstention")):
        limitations.append(
            "No direct answer was generated; the displayed records are retrieval matches, not answer evidence."
        )

    return {
        "query": original,
        "category": category,
        "category_label": CATEGORY_LABELS[category],
        "search_query_english": search_query,
        "detected_language": lang["name"],
        "language_detection": lang,
        "translation_ready": translator.enabled,
        "translation_note": translation_note,
        "answer": answer,
        "answer_mode": answer_mode_setting,
        "answer_language": answer_translation_status,
        "answer_citations": answer_citations,
        "summary": (
            f"{CATEGORY_LABELS[category]}: retrieved {len(hits)} evidence record(s) from "
            f"{len(sections)} source collection(s). "
            + (
                "The answer is general AI output, not based on these local records."
                if str(answer_mode_setting).startswith("General AI answer")
                else (
                    "No direct answer was generated; records below are search matches only."
                    if str(answer_mode_setting).startswith(("grounded abstention", "Grounded abstention"))
                    else "The answer uses only the local records shown below."
                )
            )
        ),
        "sections": sections,
        "sources": sources,
        "dataset_status": ready,
        "limitations": limitations,
        "xai_data": xai_data,
    }
