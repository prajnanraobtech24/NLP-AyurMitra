import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.download_datasets import _normalise_label, _who_download_candidates
from bs4 import BeautifulSoup
from scripts.download_datasets import _extract_target_from_container


class DownloaderParsingTests(unittest.TestCase):
    def test_imppat_label_punctuation_is_normalized(self):
        actual = _normalise_label("Plant - Therapeutic use Association")
        expected = _normalise_label("plant therapeutic use association")
        self.assertEqual(actual, expected)

    def test_who_download_link_without_pdf_extension_is_found(self):
        html = """
        <html><body>
        <a href="https://iris.who.int/server/api/core/bitstreams/example-id/content">Download (4.4 MB)</a>
        </body></html>
        """
        urls = _who_download_candidates(html, "https://www.who.int/publications/i/item/9789240064935")
        self.assertEqual(urls, ["https://iris.who.int/server/api/core/bitstreams/example-id/content"])

    def test_imppat_data_url_is_found(self):
        soup = BeautifulSoup(
            '<tr><td>Plant - Therapeutic use Association</td>'
            '<td><button data-url="/files/therapeutic_use.csv">Download</button></td></tr>',
            "html.parser",
        )
        target = _extract_target_from_container(soup.tr, "https://cb.imsc.res.in/imppat/download")
        self.assertEqual(target, "https://cb.imsc.res.in/files/therapeutic_use.csv")


if __name__ == "__main__":
    unittest.main()
