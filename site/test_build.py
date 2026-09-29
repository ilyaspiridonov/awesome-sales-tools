"""Focused checks for README coverage and safe static HTML generation."""

from html.parser import HTMLParser
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import build


class PageElements(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.entries = []
        self.sections = []
        self.links = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "li" and attrs.get("class") == "tool-entry":
            self.entries.append(attrs)
        if tag == "section":
            self.sections.append(attrs)
        if tag == "a":
            self.links.append(attrs["href"])


class BuildTests(unittest.TestCase):
    def test_every_readme_entry_and_category_is_rendered(self):
        source = (build.ROOT / "README.md").read_text(encoding="utf-8")
        document = build.parse_readme(source)
        page = PageElements(build.render_sections(document))
        source_entries = re.findall(r"^- \[([^\]]+)\]\((\S+)\) - (.+)$", source, re.MULTILINE)
        headings = re.findall(r"^## (.+)$", source, re.MULTILINE)
        categories = [heading for heading in headings if heading not in {"Contents", "Footnotes", "Related Resources"}]
        resources = re.search(r"^## Related Resources\n(.*?)(?=^## |\Z)", source, re.MULTILINE | re.DOTALL)
        resource_count = len(re.findall(r"^- \[", resources[1], re.MULTILINE)) if resources else 0
        self.assertEqual(len(page.entries), len(source_entries))
        self.assertEqual(document.tool_count, len(source_entries) - resource_count)
        self.assertEqual(document.category_count, len(categories))
        self.assertEqual(len(page.sections), len(categories) + bool(resources))
        self.assertEqual([section["id"] for section in page.sections], [section.slug for section in document.sections])
        if resources:
            self.assertEqual(next(section for section in page.sections if section["id"] == "related-resources")["data-kind"], "resource")
        for name, url, description in source_entries:
            self.assertIn(url, page.links)
            self.assertTrue(any(entry["data-search"].startswith(name + " ") for entry in page.entries))
            for nested_url in re.findall(r"\[[^\]]+\]\((https?://[^()\s]+)\)", description):
                self.assertIn(nested_url, page.links)

    def test_html_is_escaped_in_names_descriptions_and_search(self):
        document = build.parse_readme(
            '# A & B\n\n## CRM\n\n- [<Sales>](https://example.com/?a=1&b=2) - '
            '<script>alert("x")</script> & **helpful** [source](https://example.org)\n'
        )
        rendered = build.render_sections(document)
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;Sales&gt;", rendered)
        self.assertIn("<strong>helpful</strong>", rendered)
        page = PageElements(rendered)
        self.assertEqual(page.links, ["https://example.com/?a=1&b=2", "https://example.org"])
        self.assertIn('<script>alert("x")</script>', page.entries[0]["data-search"])

    def test_unsafe_urls_are_rejected(self):
        for url in ("javascript:alert(1)", "data:text/html,hello", "//evil.example", "https://good.example\\@evil.example", "https://name:secret@example.com"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                build.inline_markdown(f"[link]({url})")
        with self.assertRaises(ValueError):
            build.parse_readme("# Title\n\n## CRM\n\n- [Bad](javascript:alert(1)) - Unsafe.\n")

    def test_relative_links_and_maintainer_link(self):
        document = build.parse_readme(
            "# Tools\n\n> A directory.\n\nRead the [guide](contributing.md).\n\n"
            "## CRM\n\n- [Example](https://example.com) - A sales tool.\n\n"
            "## Footnotes\n\nMaintained by a contributor at RevManic.\n"
        )
        intro = build.render_page(document, "{{INTRO}}")
        self.assertIn(f'href="{build.REPO_URL}/blob/main/contributing.md"', intro)
        self.assertIn('at <a href="https://revmanic.com">RevManic</a>.', build.render_footer(document))

    def test_duplicate_anchors_and_entries_fail(self):
        prefix = "# Title\n\n## CRM\n\n- [First](https://example.com) - Description.\n\n"
        for suffix in (
            "## CRM!\n\n- [Second](https://other.example) - Description.\n",
            "## Other\n\n- [first](https://other.example) - Description.\n",
            "## Other\n\n- [Second](https://example.com/) - Description.\n",
        ):
            with self.subTest(suffix=suffix), self.assertRaisesRegex(ValueError, "Duplicate"):
                build.parse_readme(prefix + suffix)

    def test_malformed_entries_fail_instead_of_disappearing(self):
        with self.assertRaisesRegex(ValueError, "Expected a tool entry"):
            build.parse_readme("# Title\n\n## CRM\n\n- Tool without a link\n")
        with self.assertRaisesRegex(ValueError, "Contents links must match"):
            build.parse_readme("# Title\n\n## Contents\n\n- [CRM](#wrong)\n\n## CRM\n\n- [Tool](https://example.com) - Description.\n")

    def test_build_writes_static_assets_and_sitemap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Title\n\n## CRM\n\n- [Tool](https://example.com) - Description.\n", encoding="utf-8")
            site = root / "site"
            site.mkdir()
            (site / "template.html").write_text("{{TITLE}} {{TOOL_COUNT}} {{CATEGORY_COUNT}} {{SITE_URL}} {{SECTIONS}}", encoding="utf-8")
            for name in ("style.css", "search.js", "revmanic-icon.png"):
                (site / name).write_text(name, encoding="utf-8")
            fonts = {
                "hanken-grotesk-latin-variable.woff2": b"wOF2\x00\xffhanken",
                "unbounded-latin-variable.woff2": b"wOF2\x00\xffunbounded",
                "HankenGrotesk-OFL.txt": b"Hanken Grotesk license",
                "Unbounded-OFL.txt": b"Unbounded license",
            }
            (site / "fonts").mkdir()
            for name, content in fonts.items():
                (site / "fonts" / name).write_bytes(content)
            with patch.dict("os.environ", {"PAGES_URL": "https://example.org/sales"}):
                build.build(root)
            output = root / "_site"
            self.assertIn("Title 1 1 https://example.org/sales/", (output / "index.html").read_text(encoding="utf-8"))
            self.assertIn("<loc>https://example.org/sales/</loc>", (output / "sitemap.xml").read_text(encoding="utf-8"))
            self.assertTrue((output / ".nojekyll").exists())
            self.assertEqual((output / "search.js").read_text(encoding="utf-8"), "search.js")
            for name, content in fonts.items():
                with self.subTest(font_asset=name):
                    self.assertEqual((output / "fonts" / name).read_bytes(), content)


if __name__ == "__main__":
    unittest.main()
