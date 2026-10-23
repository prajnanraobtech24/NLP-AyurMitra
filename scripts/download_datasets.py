from __future__ import annotations

import re
import io
import zipfile
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/pdf,application/octet-stream,*/*;q=0.8",
}
TIMEOUT = 60
SOURCES = {
    "who_page": "https://www.who.int/publications/i/item/9789240064935",
    "who_pdf": "https://iris.who.int/bitstream/handle/10665/365543/9789240064935-eng.pdf?sequence=1",
    "columbia_page": "https://impact.dbmi.columbia.edu/~friedma/Projects/DiseaseSymptomKB/index.html",
    "columbia_legacy_page": "https://people.dbmi.columbia.edu/~friedma/Projects/DiseaseSymptomKB/index.html",
    "namaste_ayurveda_xlsx": "https://namaste.ayush.gov.in/admin/assets/excel/namaste/ayu_sat_table_combined.xlsx",
    "imppat_download_page": "https://cb.imsc.res.in/imppat/download",
}


def fetch(url: str, referer: str | None = None) -> requests.Response:
    headers = dict(HEADERS)
    if referer:
        headers["Referer"] = referer
    response = requests.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
    response.raise_for_status()
    return response


def valid_file(data: bytes, expected: str | None, minimum_bytes: int, content_type: str = "") -> bool:
    """Validate both size and file signature so an HTML error is never saved as a dataset."""
    if len(data) < minimum_bytes:
        return False
    if expected == "pdf":
        return data.startswith(b"%PDF")
    if expected == "xlsx":
        if not data.startswith(b"PK\x03\x04"):
            return False
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = set(archive.namelist())
                return "xl/workbook.xml" in names and "[Content_Types].xml" in names
        except (zipfile.BadZipFile, OSError):
            return False
    if expected == "html":
        head = data[:3000].lower()
        return b"<html" in head or b"<!doctype html" in head
    if expected == "csv":
        head = data[:1000].lstrip().lower()
        return not (head.startswith(b"<!doctype html") or b"<html" in head[:500])
    return True


def download_file(
    url: str,
    destination: Path,
    minimum_bytes: int = 1000,
    expected: str | None = None,
    force: bool = False,
    referer: str | None = None,
) -> bool:
    if destination.exists() and not force:
        try:
            old = destination.read_bytes()
            if valid_file(old, expected, minimum_bytes):
                print(f"[exists] {destination.relative_to(ROOT)} ({len(old):,} bytes)")
                return True
            print(f"[warning] Existing {destination.name} failed file-type validation; retrying download")
        except OSError:
            pass
    try:
        response = fetch(url, referer=referer)
        data = response.content
        content_type = response.headers.get("content-type", "")
        if not valid_file(data, expected, minimum_bytes, content_type):
            raise ValueError(
                f"response failed {expected or 'file'} validation "
                f"(size={len(data)}, content-type={content_type}, final_url={response.url})"
            )
        destination.write_bytes(data)
        print(f"[downloaded] {destination.relative_to(ROOT)} ({len(data):,} bytes)")
        return True
    except Exception as exc:
        print(f"[warning] {destination.name} from {url}: {exc}")
        return False


def _normalise_label(text: str) -> str:
    """Normalize punctuation so 'Plant - Therapeutic use Association' matches."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _who_download_candidates(html: str, page_url: str) -> list[str]:
    """Find WHO download anchors even when the target URL has no '.pdf' suffix."""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = urljoin(page_url, anchor["href"])
        label = (anchor.get_text(" ", strip=True) + " " + href).lower()
        if "download" in label or "9789240064935" in label or "365543" in label:
            if "iris.who.int" in href or "apps.who.int/iris" in href:
                candidates.append(href)
    return list(dict.fromkeys(candidates))


def find_local_who_pdf() -> Path | None:
    """Return a valid WHO PDF using either the current or legacy project filename."""
    for candidate in (RAW / "who_ayurveda_terminologies.pdf", RAW / "WHO.pdf"):
        try:
            if candidate.is_file() and candidate.stat().st_size > 100_000 and candidate.read_bytes()[:5] == b"%PDF-":
                return candidate
        except OSError:
            continue
    return None


def download_who_pdf() -> bool:
    """Reuse an existing valid WHO PDF before attempting a network download.

    The initial AyurMitra project used data/raw/WHO.pdf. Keep that filename
    supported so an already downloaded source is not ignored or overwritten.
    """
    existing = find_local_who_pdf()
    if existing:
        print(f"[exists] Reusing valid WHO PDF: {existing.relative_to(ROOT)} ({existing.stat().st_size:,} bytes)")
        return True

    destination = RAW / "who_ayurveda_terminologies.pdf"
    # Remove only an invalid standardized placeholder. Never delete a user's legacy WHO.pdf.
    if destination.exists():
        try:
            if not destination.read_bytes().startswith(b"%PDF-"):
                destination.unlink()
                print("[cleaned] Removed invalid WHO PDF placeholder (it was not a real PDF)")
        except OSError:
            pass
    # The current WHO page links to an API endpoint without a .pdf extension.
    urls = [
        "https://iris.who.int/server/api/core/bitstreams/bd4c0a7d-f7b2-420e-8c93-0ecb9009f718/content",
        "https://iris.who.int/bitstream/handle/10665/365543/9789240064935-eng.pdf?isAllowed=y&sequence=1",
        SOURCES["who_pdf"],
        "https://iris.who.int/bitstream/handle/10665/365543/9789240064935-eng.pdf",
        "https://apps.who.int/iris/bitstream/handle/10665/365543/9789240064935-eng.pdf",
    ]
    for url in urls:
        if download_file(
            url, destination, minimum_bytes=100_000, expected="pdf",
            force=True, referer=SOURCES["who_page"]
        ):
            return True

    try:
        page = fetch(SOURCES["who_page"])
        for url in _who_download_candidates(page.text, SOURCES["who_page"]):
            if download_file(
                url, destination, minimum_bytes=100_000, expected="pdf",
                force=True, referer=SOURCES["who_page"]
            ):
                return True
    except Exception as exc:
        print(f"[warning] Could not discover WHO PDF from publication page: {exc}")

    print(
        f"[manual action] WHO rejected automated downloads. Open {SOURCES['who_page']}, "
        "click 'Download (4.4 MB)', then save the actual PDF as "
        "data/raw/who_ayurveda_terminologies.pdf. The file must begin with a PDF signature "
        "and open in a PDF reader; do not rename an HTML error page."
    )
    return False


def _extract_target_candidates(container, page_url: str) -> list[str]:
    """Return ranked possible file URLs inside an official download row/button."""
    elements = [container, *container.find_all(True)]
    candidates: list[tuple[int, str]] = []
    file_ext = re.compile(r"\.(?:csv|tsv|txt|xlsx?|zip)(?:[?#].*)?$", re.I)
    for element in elements:
        label = (element.get_text(" ", strip=True) + " " + str(element.get("aria-label", ""))).lower()
        for attr in ("href", "data-href", "data-url", "data-download", "formaction", "data-file", "data-path"):
            value = (element.get(attr) or "").strip()
            if not value or value.startswith(("#", "javascript:", "mailto:")):
                continue
            absolute = urljoin(page_url, value)
            score = (5 if file_ext.search(absolute) else 0) + (4 if "download" in label else 0)
            if absolute.startswith(("http://", "https://")):
                candidates.append((score, absolute))
        onclick = element.get("onclick", "")
        # Include URLs and server paths even when the download endpoint has no file extension.
        for value in re.findall(r"['\"]((?:https?://|/)[^'\"]+)['\"]", onclick):
            absolute = urljoin(page_url, value)
            score = (5 if file_ext.search(absolute) else 0) + (4 if "download" in label or "download" in onclick.lower() else 0)
            candidates.append((score, absolute))
        for value in re.findall(r"https?://[^'\"\s)]+", onclick):
            candidates.append((5, value))
    # De-duplicate while preserving the highest score, then return most likely files first.
    unique: dict[str, int] = {}
    for score, url in candidates:
        unique[url] = max(score, unique.get(url, -1))
    return [url for url, _ in sorted(unique.items(), key=lambda item: (-item[1], item[0]))]


def _extract_target_from_container(container, page_url: str) -> str | None:
    """Backward-compatible single best candidate helper used by tests."""
    candidates = _extract_target_candidates(container, page_url)
    return candidates[0] if candidates else None


def _download_imppat_target(url: str, basename: str, page_url: str) -> bool:
    try:
        response = fetch(url, referer=page_url)
        data = response.content
        if len(data) < 1000:
            raise ValueError(f"download unexpectedly small ({len(data)} bytes)")
        content_type = response.headers.get("content-type", "").lower()
        if data.startswith(b"PK\x03\x04"):
            # Preserve ZIPs as ZIPs. XLSX is also a ZIP container, so only use .xlsx
            # when the URL or MIME type explicitly identifies a spreadsheet.
            ext = ".xlsx" if response.url.lower().endswith(".xlsx") or "spreadsheet" in content_type else ".zip"
        elif data.startswith(b"\xd0\xcf\x11\xe0"):
            ext = ".xls"
        elif b"<html" in data[:2000].lower() or b"<!doctype html" in data[:2000].lower():
            raise ValueError(f"server returned HTML instead of the dataset (content-type={content_type})")
        else:
            ext = ".csv"
        output = RAW / (basename + ext)
        output.write_bytes(data)
        print(f"[downloaded] {output.relative_to(ROOT)} ({len(data):,} bytes)")
        return True
    except Exception as exc:
        print(f"[warning] IMPPAT source download failed for {url}: {exc}")
        return False


def download_imppat() -> None:
    """Find the two lightweight IMPPAT files using punctuation-insensitive row matching."""
    page_url = SOURCES["imppat_download_page"]
    try:
        response = fetch(page_url)
        soup = BeautifulSoup(response.text, "html.parser")
        wanted = [
            ("plant therapeutic use association", "imppat_plant_therapeutic_use"),
            ("information on medicinal plants in imppat", "imppat_plant_info"),
        ]
        for phrase, basename in wanted:
            existing = [
                p for p in RAW.iterdir()
                if p.is_file() and p.stem.lower().startswith(basename) and p.stat().st_size > 1000
            ]
            if existing:
                print(f"[exists] {basename} source file already present: {existing[0].name}")
                continue

            target_urls: list[str] = []
            wanted_label = _normalise_label(phrase)
            # Prefer exact table rows first; broader divs can contain several download rows.
            matching_rows = []
            for row in soup.find_all("tr"):
                row_label = _normalise_label(" ".join(row.stripped_strings))
                if wanted_label in row_label:
                    matching_rows.append((len(row_label), row))
            for _, row in sorted(matching_rows, key=lambda item: item[0]):
                target_urls.extend(_extract_target_candidates(row, page_url))
            # Some page versions use cards rather than a table; inspect only compact matching cards.
            if not target_urls:
                matching_containers = []
                for container in soup.find_all(["div", "li"]):
                    label = _normalise_label(" ".join(container.stripped_strings))
                    if wanted_label in label and len(label) < 500:
                        matching_containers.append((len(label), container))
                for _, container in sorted(matching_containers, key=lambda item: item[0]):
                    target_urls.extend(_extract_target_candidates(container, page_url))
            target_urls = list(dict.fromkeys(target_urls))
            downloaded = False
            for target_url in target_urls:
                if _download_imppat_target(target_url, basename, page_url):
                    downloaded = True
                    break
            if not downloaded:
                print(
                    f"[manual action] Could not automatically retrieve '{phrase}'. Open {page_url}, "
                    f"click the matching Download button, and save the original file as "
                    f"data/raw/{basename} with its actual extension. Do not rename an HTML page as a dataset."
                )
    except Exception as exc:
        print(f"[warning] Could not inspect IMPPAT batch page: {exc}")
        print(f"[manual action] Use the official page {page_url} and download the two lightweight tables.")
        print("Required: 'Plant - Therapeutic use Association' and 'Information on Medicinal Plants in IMPPAT'.")


def download_columbia_page() -> bool:
    """Download the Columbia disease-symptom page from current or legacy host.

    A successful HTTP response is not sufficient: the page must actually look
    like the expected source, otherwise keep trying and do not save an error page.
    """
    destination = RAW / "columbia_disease_symptom_source.html"
    if destination.exists():
        try:
            text = destination.read_text(encoding="utf-8", errors="replace").lower()
            if "disease" in text and "symptom" in text and ("occurrence" in text or "count" in text):
                print(f"[exists] Valid-looking Columbia source page: {destination.relative_to(ROOT)}")
                return True
        except OSError:
            pass
    urls = [
        SOURCES["columbia_page"],
        SOURCES["columbia_legacy_page"],
        "http://impact.dbmi.columbia.edu/~friedma/Projects/DiseaseSymptomKB/index.html",
        "http://people.dbmi.columbia.edu/~friedma/Projects/DiseaseSymptomKB/index.html",
    ]
    for url in urls:
        try:
            response = fetch(url)
            data = response.content
            text = data[:2_000_000].decode("utf-8", errors="replace").lower()
            if not valid_file(data, "html", 1000, response.headers.get("content-type", "")):
                raise ValueError("response is not HTML")
            if "disease" not in text or "symptom" not in text or not ("occurrence" in text or "count" in text):
                raise ValueError("page does not contain expected disease/symptom table labels")
            destination.write_bytes(data)
            print(f"[downloaded] {destination.relative_to(ROOT)} ({len(data):,} bytes) from {response.url}")
            return True
        except Exception as exc:
            print(f"[warning] Columbia source {url}: {exc}")
    print("[manual action] Could not retrieve the Columbia page automatically. Open the source link in docs/DATA_SOURCES.md and save the page as data/raw/columbia_disease_symptom_source.html only if it contains the actual disease-symptom table.")
    return False


def main() -> int:
    print("AyurMitra dataset downloader — original sources are saved locally; large model weights are not required.\n")
    download_who_pdf()
    download_columbia_page()
    download_file(
        SOURCES["namaste_ayurveda_xlsx"],
        RAW / "namaste_ayurveda_sat_combined.xlsx",
        expected="xlsx",
    )
    download_imppat()
    print("\nNext: python scripts/prepare_datasets.py")
    print("AYUSH Research Portal is a searchable research catalogue; it is not treated as a bulk dataset.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
