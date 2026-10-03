"""Validate a case and prepare the complete available paper text."""

from __future__ import annotations

import json
import re
import ssl
from html.parser import HTMLParser
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

import certifi
from PIL import Image

from paperplay.pdf_reader import PaperPage, pages_as_text, read_pdf
from paperplay.visuals import PageSheet, make_image_sheets


SOURCE_FIELDS = (
    "excerpt", "paper_excerpt", "source_excerpt", "excerpt_text",
    "source_text", "paper_text", "source_material", "text", "content",
)
MAX_INPUT_BYTES = 2_000_000
MAX_DOWNLOAD_BYTES = 12_000_000
FETCH_TIMEOUT_SECONDS = 20.0
MAX_FIGURE_BYTES = 4_000_000


@dataclass(frozen=True)
class PreparedPaper:
    text: str
    field: str
    method: str
    pages: tuple[PaperPage, ...] = ()
    raw_pdf: bytes | None = None
    figure_sheets: tuple[PageSheet, ...] = ()
    html_tables: int = 0


def html_url_for_source(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.hostname in ("arxiv.org", "www.arxiv.org") and parsed.path.startswith(("/abs/", "/pdf/", "/html/")):
        identifier = parsed.path.split("/", 2)[2]
        if identifier:
            return f"{parsed.scheme}://arxiv.org/html/{identifier}"
    return None


def pdf_url_for_source(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.hostname in ("arxiv.org", "www.arxiv.org") and parsed.path.startswith(("/abs/", "/html/", "/pdf/")):
        identifier = parsed.path.split("/", 2)[2]
        return f"{parsed.scheme}://arxiv.org/pdf/{identifier}"
    if parsed.path.lower().endswith(".pdf"):
        return url
    return None


def load_case(path: Path) -> dict:
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("Input JSON exceeds the 2 MB safety limit.")
    with path.open("r", encoding="utf-8") as handle:
        case = json.load(handle)
    if not isinstance(case, dict):
        raise ValueError("The input must be a JSON object.")
    for field in ("source_url", "focus", "audience"):
        if not isinstance(case.get(field), str) or not case[field].strip():
            raise ValueError(f"'{field}' must be a nonempty string.")
    parsed = urlparse(case["source_url"].strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("'source_url' must be an HTTP(S) URL.")
    return case


def _source_value(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str) and item.strip():
                parts.append(item.strip())
            elif isinstance(item, dict):
                for key in ("text", "excerpt", "content"):
                    if isinstance(item.get(key), str) and item[key].strip():
                        parts.append(item[key].strip())
                        break
        if parts:
            return "\n\n".join(parts)
    return None


def extract_source(case: dict) -> tuple[str, str]:
    """Read an optional excerpt supplied with an assessment case."""
    containers = [("", case)]
    for key in ("paper", "source", "document"):
        if isinstance(case.get(key), dict):
            containers.append((key + ".", case[key]))
    for prefix, container in containers:
        for field in SOURCE_FIELDS:
            text = _source_value(container.get(field))
            if text:
                return text, prefix + field
        text = _source_value(container.get("excerpts"))
        if text:
            return text, prefix + "excerpts"
    raise ValueError("No supplied paper excerpt was found.")


class _HTMLText(HTMLParser):
    BLOCKS = frozenset((
        "article", "main", "section", "div", "p", "br", "h1", "h2", "h3",
        "h4", "h5", "h6", "li", "tr", "table", "blockquote",
    ))
    SKIP = frozenset(("script", "style", "nav", "footer", "header", "noscript"))

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0
        self.figure_depth = 0
        self.images: list[tuple[str, str]] = []
        self.table_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag == "figure":
            self.figure_depth += 1
        if tag == "table":
            self.table_count += 1
        if tag in ("td", "th"):
            self.parts.append(" | ")
        if tag == "img" and self.figure_depth:
            values = dict(attrs)
            src = values.get("src")
            if src:
                alt = values.get("alt") or ""
                self.images.append((src, alt))
                self.parts.append(f"\n[Figure image {len(self.images)}: {alt}]\n")
        if tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag == "figure" and self.figure_depth:
            self.figure_depth -= 1
        if tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)


def _download(url: str, limit: int = MAX_DOWNLOAD_BYTES) -> tuple[bytes, str, str]:
    request = Request(url, headers={"User-Agent": "PaperPlayground/0.1 (research education)"})
    try:
        with urlopen(
            request, timeout=FETCH_TIMEOUT_SECONDS,
            context=ssl.create_default_context(cafile=certifi.where()),
        ) as response:
            if urlparse(response.geturl()).scheme not in ("http", "https"):
                raise ValueError("Paper URL redirected to a non-HTTP(S) location.")
            content_type = response.headers.get_content_type()
            final_url = response.geturl()
            data = response.read(limit + 1)
    except HTTPError as exc:
        raise ValueError(f"Paper retrieval returned HTTP {exc.code}.") from None
    except (URLError, TimeoutError) as exc:
        raise ValueError(f"Paper retrieval failed: {type(exc).__name__}.") from None
    if len(data) > limit:
        raise ValueError("Paper download exceeds the configured size limit.")
    return data, content_type, final_url


def _prepare_html(data: bytes, final_url: str) -> PreparedPaper:
    parsed_url = urlparse(final_url)
    if parsed_url.hostname in ("arxiv.org", "www.arxiv.org") and not parsed_url.path.startswith("/html/"):
        raise ValueError("arXiv did not return a full-text HTML paper.")
    parser = _HTMLText()
    parser.feed(data.decode("utf-8", errors="replace"))
    text = "".join(parser.parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]*\n+", "\n\n", text).strip()
    if len(text) < 200:
        raise ValueError("The HTML did not yield enough full-paper text.")
    images = []
    for src, _alt in parser.images:
        image_url = urljoin(final_url, src)
        if urlparse(image_url).scheme not in ("http", "https"):
            raise ValueError("Figure image has an unsupported URL.")
        raw, _, _ = _download(image_url, MAX_FIGURE_BYTES)
        try:
            with Image.open(BytesIO(raw)) as image:
                rendered = image.convert("RGB")
                images.append(rendered.copy())
                rendered.close()
        except (OSError, ValueError) as exc:
            raise ValueError("A figure image could not be decoded.") from exc
    try:
        sheets = make_image_sheets(tuple(images), label="Figure image")
    finally:
        for image in images:
            image.close()
    return PreparedPaper(text, "source_url", "html_fetch",
                         figure_sheets=sheets, html_tables=parser.table_count)


def _prepare_url(url: str) -> PreparedPaper:
    data, content_type, final_url = _download(url)
    if data.startswith(b"%PDF-") or content_type == "application/pdf":
        pages = read_pdf(data)
        text = pages_as_text(pages)
        return PreparedPaper(text, "source_url", "pdf_fetch", pages, data)
    return _prepare_html(data, final_url)


def retrieve_source_url(url: str) -> PreparedPaper:
    """Prefer full arXiv HTML, falling back to the PDF on conversion failure."""
    html_url = html_url_for_source(url)
    if html_url:
        try:
            paper = _prepare_url(html_url)
            if paper.method != "html_fetch":
                raise ValueError("arXiv HTML URL did not return HTML.")
            return paper
        except ValueError:
            pdf_url = pdf_url_for_source(url)
            if pdf_url is None:
                raise
            return _prepare_url(pdf_url)
    return _prepare_url(url)


def prepare_paper(case: dict) -> PreparedPaper:
    """Keep all extracted text so the model decides which material matters."""
    try:
        text, field = extract_source(case)
        return PreparedPaper(text, field, "supplied_case_text")
    except ValueError:
        return retrieve_source_url(case["source_url"])
