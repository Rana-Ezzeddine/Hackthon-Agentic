"""Loss-aware PDF representation: text, tables, images, and full page views."""

from __future__ import annotations

from dataclasses import dataclass

import pymupdf


@dataclass(frozen=True)
class EmbeddedImage:
    bbox: tuple[float, float, float, float]
    media_type: str
    data: bytes


@dataclass(frozen=True)
class PaperPage:
    number: int
    text: str
    tables: tuple[tuple[tuple[str, ...], ...], ...]
    embedded_images: tuple[EmbeddedImage, ...]
    drawing_count: int
    rendered_jpeg: bytes
    table_extraction_error: str | None = None


def read_pdf(data: bytes) -> tuple[PaperPage, ...]:
    """Render every page so vector figures and image-only tables are retained."""
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ValueError(f"Could not open PDF: {type(exc).__name__}.") from None

    pages: list[PaperPage] = []
    try:
        if document.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported.")
        for page_index, page in enumerate(document):
            page_text = page.get_text("text", sort=True).strip()
            tables = []
            table_error = None
            try:
                for table in page.find_tables().tables:
                    rows = tuple(
                        tuple((cell or "").strip() for cell in row)
                        for row in table.extract()
                    )
                    if rows:
                        tables.append(rows)
            except Exception as exc:
                # The page render still preserves an undetected table visually.
                table_error = type(exc).__name__

            images = []
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") != 1 or not block.get("image"):
                    continue
                extension = block.get("ext", "png").lower()
                media_type = {
                    "jpg": "image/jpeg", "jpeg": "image/jpeg",
                    "png": "image/png", "gif": "image/gif",
                    "webp": "image/webp", "bmp": "image/bmp",
                    "tif": "image/tiff", "tiff": "image/tiff",
                }.get(extension, "application/octet-stream")
                images.append(EmbeddedImage(
                    bbox=tuple(float(x) for x in block["bbox"]),
                    media_type=media_type,
                    data=block["image"],
                ))

            # A rendered view also preserves charts, equations, diagrams, and
            # vector drawings that are not embedded raster images.
            rendered = page.get_pixmap(dpi=144, alpha=False).tobytes(
                "jpeg", jpg_quality=75
            )
            pages.append(PaperPage(
                number=page_index + 1,
                text=page_text,
                tables=tuple(tables),
                embedded_images=tuple(images),
                drawing_count=len(page.get_drawings()),
                rendered_jpeg=rendered,
                table_extraction_error=table_error,
            ))
    except Exception as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError(f"Could not prepare PDF page: {type(exc).__name__}.") from None
    finally:
        document.close()
    if not pages:
        raise ValueError("The PDF has no pages.")
    return tuple(pages)


def pages_as_text(pages: tuple[PaperPage, ...]) -> str:
    parts = []
    for page in pages:
        part = f"[Page {page.number}]\n{page.text}"
        if page.tables:
            rows = []
            for table_index, table in enumerate(page.tables, 1):
                rows.append(f"[Table {table_index} on page {page.number}]")
                rows.extend(" | ".join(row) for row in table)
            part += "\n" + "\n".join(rows)
        if page.table_extraction_error:
            part += f"\n[Table structure could not be extracted on page {page.number}; inspect page image.]"
        if page.embedded_images or page.drawing_count:
            part += (
                f"\n[Visual content on page {page.number}: "
                f"{len(page.embedded_images)} embedded images, "
                f"{page.drawing_count} vector drawing elements; "
                "see the rendered page image.]"
            )
        parts.append(part)
    return "\n\n".join(parts)
