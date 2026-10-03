"""Group PDF pages or HTML figures into bounded vision request batches."""

from __future__ import annotations

import base64
import math
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageDraw

from paperplay.pdf_reader import PaperPage


MAX_VISUAL_CALLS = 4
MAX_IMAGES_PER_CALL = 8


@dataclass(frozen=True)
class PageSheet:
    page_numbers: tuple[int, ...]
    jpeg: bytes


def make_page_sheets(pages: tuple[PaperPage, ...]) -> tuple[PageSheet, ...]:
    """Include every page; combine pages only to respect request limits."""
    if not pages:
        return ()
    max_sheets = MAX_VISUAL_CALLS * MAX_IMAGES_PER_CALL
    pages_per_sheet = max(2, math.ceil(len(pages) / max_sheets))
    sheets = []
    for start in range(0, len(pages), pages_per_sheet):
        group = pages[start:start + pages_per_sheet]
        images = [Image.open(BytesIO(page.rendered_jpeg)).convert("RGB") for page in group]
        columns = min(2, len(images))
        rows = math.ceil(len(images) / columns)
        width = max(image.width for image in images)
        height = max(image.height for image in images)
        canvas = Image.new("RGB", (columns * width, rows * (height + 28)), "white")
        draw = ImageDraw.Draw(canvas)
        for position, (page, image) in enumerate(zip(group, images)):
            x = (position % columns) * width
            y = (position // columns) * (height + 28)
            draw.text((x + 8, y + 7), f"PDF page {page.number}", fill="black")
            canvas.paste(image, (x, y + 28))
        output = BytesIO()
        canvas.save(output, format="JPEG", quality=76, optimize=True)
        sheets.append(PageSheet(tuple(page.number for page in group), output.getvalue()))
        for image in images:
            image.close()
        canvas.close()
    return tuple(sheets)


def make_image_sheets(images: tuple[Image.Image, ...], label: str) -> tuple[PageSheet, ...]:
    """Include every HTML figure, combining images only to bound request count."""
    if not images:
        return ()
    max_sheets = MAX_VISUAL_CALLS * MAX_IMAGES_PER_CALL
    images_per_sheet = max(1, math.ceil(len(images) / max_sheets))
    sheets = []
    for start in range(0, len(images), images_per_sheet):
        group = images[start:start + images_per_sheet]
        scaled = []
        for image in group:
            copy = image.copy()
            copy.thumbnail((1400, 1400))
            scaled.append(copy)
        columns = min(2, len(scaled))
        rows = math.ceil(len(scaled) / columns)
        width = max(image.width for image in scaled)
        height = max(image.height for image in scaled)
        canvas = Image.new("RGB", (columns * width, rows * (height + 28)), "white")
        draw = ImageDraw.Draw(canvas)
        numbers = tuple(range(start + 1, start + 1 + len(group)))
        for position, (number, image) in enumerate(zip(numbers, scaled)):
            x = (position % columns) * width
            y = (position // columns) * (height + 28)
            draw.text((x + 8, y + 7), f"{label} {number}", fill="black")
            canvas.paste(image, (x, y + 28))
        output = BytesIO()
        canvas.save(output, format="JPEG", quality=76, optimize=True)
        sheets.append(PageSheet(numbers, output.getvalue()))
        for image in scaled:
            image.close()
        canvas.close()
    return tuple(sheets)


def visual_batches(sheets: tuple[PageSheet, ...]) -> tuple[tuple[PageSheet, ...], ...]:
    return tuple(
        sheets[i:i + MAX_IMAGES_PER_CALL]
        for i in range(0, len(sheets), MAX_IMAGES_PER_CALL)
    )


def sheet_data_url(sheet: PageSheet) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(sheet.jpeg).decode("ascii")
