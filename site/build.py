#!/usr/bin/env python3
"""Build the Pages directory from README.md using only the Python standard library."""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
import os
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import urljoin, urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parent.parent
REPO_URL = "https://github.com/ilyaspiridonov/awesome-sales-tools"
DEFAULT_SITE_URL = "https://ilyaspiridonov.github.io/awesome-sales-tools/"
ENTRY = re.compile(r"- \[([^\]\n]+)\]\((\S+)\) - (.+)")
CONTENTS_ENTRY = re.compile(r"- \[([^\]\n]+)\]\(#([^\s)]+)\)")
BADGE = re.compile(r"\s+\[!\[[^\]]*\]\([^\s)]+\)\]\([^\s)]+\)$")
PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")


@dataclass
class Entry:
    name: str
    url: str
    description: str


@dataclass
class Section:
    title: str
    slug: str
    kind: str = "tools"
    descriptions: list[str] = field(default_factory=list)
    entries: list[Entry] = field(default_factory=list)


@dataclass
class Document:
    title: str
    intro: list[str]
    sections: list[Section]
    footer: list[str]

    @property
    def tool_count(self) -> int:
        return sum(len(section.entries) for section in self.sections if section.kind == "tools")

    @property
    def category_count(self) -> int:
        return sum(section.kind == "tools" for section in self.sections)


def heading_slug(title: str) -> str:
    """Use GitHub's anchor form for the plain-text headings in this README."""
    return re.sub(r"\s", "-", re.sub(r"[^\w\s-]", "", title.lower()))


def safe_url(value: str, *, absolute: bool = False) -> str:
    """Allow web links; resolve README-relative links against the source repository."""
    if not value or re.search(r"[\s\x00-\x1f\x7f\\]", value):
        raise ValueError(f"Invalid link URL: {value!r}")
    try:
        parsed = urlsplit(value)
        # Reading port also validates malformed ports and bracketed hostnames.
        _ = parsed.port
    except ValueError as error:
        raise ValueError(f"Invalid link URL: {value!r}") from error
    if parsed.scheme:
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise ValueError(f"Unsafe link URL: {value!r}")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError(f"Credentials are not allowed in link URLs: {value!r}")
        return value
    if absolute or value.startswith("//") or parsed.netloc:
        raise ValueError(f"Expected an absolute HTTP(S) link: {value!r}")
    if value.startswith("#"):
        return value
    return urljoin(f"{REPO_URL}/blob/main/", value)


def inline_markdown(source: str) -> str:
    """Render links and simple emphasis, escaping all source HTML."""
    output: list[str] = []
    position = 0
    while position < len(source):
        if source[position] == "[":
            label_end = source.find("](", position + 1)
            if label_end != -1 and "[" not in source[position + 1:label_end]:
                url_start = label_end + 2
                end = url_start
                depth = 1
                while end < len(source) and depth:
                    if source[end] == "(":
                        depth += 1
                    elif source[end] == ")":
                        depth -= 1
                    end += 1
                if depth:
                    raise ValueError(f"Unclosed Markdown link: {source!r}")
                label = source[position + 1:label_end]
                url = safe_url(source[url_start:end - 1])
                output.append(f'<a href="{escape(url, quote=True)}">{escape(label)}</a>')
                position = end
                continue
        matched = False
        for marker, tag in (("**", "strong"), ("*", "em"), ("`", "code")):
            if source.startswith(marker, position):
                end = source.find(marker, position + len(marker))
                if end > position + len(marker):
                    contents = source[position + len(marker):end]
                    rendered = escape(contents) if tag == "code" else inline_markdown(contents)
                    output.append(f"<{tag}>{rendered}</{tag}>")
                    position = end + len(marker)
                    matched = True
                    break
        if not matched:
            output.append(escape(source[position]))
            position += 1
    return "".join(output)


def plain_markdown(source: str) -> str:
    """Readable search text; link destinations are intentionally excluded."""
    source = re.sub(r"\[([^\]]+)\]\([^\s]+\)", r"\1", source)
    return re.sub(r"[*`]", "", source)


def parse_readme(source: str) -> Document:
    document = Document("", [], [], [])
    current: Section | None = None
    area = "intro"
    paragraph: list[str] = []
    headings: set[str] = set()
    names: set[str] = set()
    urls: set[str] = set()
    contents: list[tuple[str, str]] = []

    def flush_paragraph() -> None:
        if not paragraph:
            return
        value = " ".join(paragraph)
        inline_markdown(value)  # Validate links before any output is written.
        if area == "intro":
            document.intro.append(value)
        elif area == "footer":
            document.footer.append(value)
        elif area == "section" and current is not None:
            if current.entries:
                raise ValueError(f"Unexpected paragraph after entries in {current.title!r}")
            current.descriptions.append(value)
        else:
            raise ValueError("Unexpected paragraph in Contents")
        paragraph.clear()

    for line_number, raw_line in enumerate(source.splitlines(), 1):
        line = raw_line.strip()
        try:
            if not line:
                flush_paragraph()
                continue
            if line.startswith("# "):
                if document.title or document.sections or paragraph:
                    raise ValueError("Expected exactly one document title before the content")
                document.title = BADGE.sub("", line[2:]).strip()
                if not document.title:
                    raise ValueError("The document title is empty")
                continue
            if not document.title:
                raise ValueError("The README must begin with a level-one title")
            if line.startswith("## "):
                flush_paragraph()
                title = line[3:].strip()
                slug = heading_slug(title)
                if not slug:
                    raise ValueError("A section heading has no usable anchor")
                if slug in headings:
                    raise ValueError(f"Duplicate heading anchor: {slug!r}")
                headings.add(slug)
                current = None
                if title == "Contents":
                    area = "contents"
                elif title == "Footnotes":
                    area = "footer"
                else:
                    area = "section"
                    current = Section(title, slug, "resource" if title == "Related Resources" else "tools")
                    document.sections.append(current)
                continue
            if line.startswith("#"):
                raise ValueError("Only level-one and level-two Markdown headings are supported")
            if line.startswith(("- ", "* ", "+ ")):
                flush_paragraph()
                if area == "contents":
                    match = CONTENTS_ENTRY.fullmatch(line)
                    if not match:
                        raise ValueError("Malformed Contents link")
                    contents.append((match[1], match[2]))
                    continue
                match = ENTRY.fullmatch(line)
                if area != "section" or current is None or not match:
                    raise ValueError("Expected a tool entry: - [Name](https://example.com) - Description")
                name, url, description = match.groups()
                name = name.strip()
                if not name:
                    raise ValueError("A tool entry has an empty name")
                url = safe_url(url, absolute=True)
                parsed = urlsplit(url)
                url_key = urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), parsed.query, ""))
                if name.casefold() in names or url_key in urls:
                    raise ValueError(f"Duplicate tool or resource entry: {name!r}")
                inline_markdown(description)
                names.add(name.casefold())
                urls.add(url_key)
                current.entries.append(Entry(name, url, description))
                continue
            paragraph.append(line[2:] if area == "intro" and line.startswith("> ") else line)
        except ValueError as error:
            raise ValueError(f"README line {line_number}: {error}") from error
    flush_paragraph()
    if not document.title or not document.sections:
        raise ValueError("The README must contain a title and tool sections")
    for section in document.sections:
        if not section.entries:
            raise ValueError(f"Section {section.title!r} contains no entries")
    expected_contents = [(section.title, section.slug) for section in document.sections]
    if contents and contents != expected_contents:
        raise ValueError("Contents links must match the category headings and their order")
    return document


def render_nav(document: Document) -> str:
    return "\n".join(
        f'<a class="category-link" href="#{section.slug}" data-category="{section.slug}">'
        f'<span>{escape(section.title)}</span><span class="category-count">{len(section.entries)}</span></a>'
        for section in document.sections
    )


def render_sections(document: Document) -> str:
    sections = []
    for section in document.sections:
        noun = "resources" if section.kind == "resource" else "tools"
        parts = [
            f'<section class="tool-section" id="{section.slug}" data-category="{section.slug}" '
            f'data-kind="{section.kind}" aria-labelledby="{section.slug}-heading">',
            f'<header class="section-heading"><h2 id="{section.slug}-heading">{escape(section.title)}</h2>'
            f'<span class="section-count">{len(section.entries)} {noun}</span></header>',
        ]
        parts.extend(f'<p class="section-description">{inline_markdown(value)}</p>' for value in section.descriptions)
        parts.append('<ul class="tool-list">')
        for entry in section.entries:
            search = escape(f"{entry.name} {plain_markdown(entry.description)} {section.title}", quote=True)
            parts.append(
                f'<li class="tool-entry" data-search="{search}">'
                f'<a class="tool-name" href="{escape(entry.url, quote=True)}">{escape(entry.name)} '
                '<span aria-hidden="true">↗</span></a>'
                f'<p class="tool-description">{inline_markdown(entry.description)}</p></li>'
            )
        parts.extend(["</ul>", "</section>"])
        sections.append("\n".join(parts))
    return "\n".join(sections)


def render_footer(document: Document) -> str:
    paragraphs = []
    for value in document.footer:
        value = value.replace("at RevManic.", "at [RevManic](https://revmanic.com).")
        paragraphs.append(f"<p>{inline_markdown(value)}</p>")
    return "\n".join(paragraphs)


def render_page(document: Document, template: str, site_url: str = DEFAULT_SITE_URL) -> str:
    site_url = safe_url(site_url, absolute=True)
    values = {
        "TITLE": escape(document.title),
        "DESCRIPTION": escape(plain_markdown(document.intro[0] if document.intro else document.title), quote=True),
        "INTRO": "\n".join(f"<p>{inline_markdown(value)}</p>" for value in document.intro[1:]),
        "TOOL_COUNT": str(document.tool_count),
        "CATEGORY_COUNT": str(document.category_count),
        "NAV": render_nav(document),
        "SECTIONS": render_sections(document),
        "FOOTER": render_footer(document),
        "SITE_URL": escape(site_url, quote=True),
        "REPO_URL": escape(REPO_URL, quote=True),
    }
    unknown = set(PLACEHOLDER.findall(template)) - values.keys()
    if unknown:
        raise ValueError(f"Unknown template placeholders: {', '.join(sorted(unknown))}")
    return PLACEHOLDER.sub(lambda match: values[match[1]], template)


def build(root: Path = ROOT) -> Document:
    document = parse_readme((root / "README.md").read_text(encoding="utf-8"))
    site_url = safe_url(os.environ.get("PAGES_URL", DEFAULT_SITE_URL), absolute=True)
    if urlsplit(site_url).query or urlsplit(site_url).fragment:
        raise ValueError("PAGES_URL must not contain a query string or fragment")
    site_url = site_url.rstrip("/") + "/"
    site = root / "site"
    rendered = render_page(document, (site / "template.html").read_text(encoding="utf-8"), site_url)
    assets = [site / name for name in (
        "style.css", "search.js", "revmanic-icon.png",
        "fonts/hanken-grotesk-latin-variable.woff2",
        "fonts/unbounded-latin-variable.woff2",
        "fonts/HankenGrotesk-OFL.txt",
        "fonts/Unbounded-OFL.txt",
    )]
    for asset in assets:
        if not asset.is_file():
            raise ValueError(f"Missing site asset: {asset}")
    output = root / "_site"
    output.mkdir(exist_ok=True)
    (output / "index.html").write_text(rendered, encoding="utf-8")
    for asset in assets:
        destination = output / asset.relative_to(site)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(asset, destination)
    (output / ".nojekyll").write_text("", encoding="utf-8")
    (output / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{escape(site_url)}</loc></url>\n</urlset>\n",
        encoding="utf-8",
    )
    return document


def main() -> int:
    try:
        document = build()
    except (OSError, ValueError) as error:
        print(f"Build failed: {error}", file=sys.stderr)
        return 1
    print(f"Built _site/index.html: {document.tool_count} tools in {document.category_count} categories.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
