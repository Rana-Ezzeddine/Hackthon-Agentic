"""Complete, ordered paper context for model-led focus selection."""
from __future__ import annotations

import json

from .selection import PreparedSource


def prepare_full_paper(record, trace) -> PreparedSource:
    """Serialize every parsed source item; never rank or clip by focus.

    Figure bytes remain on the record and are attached separately as image
    parts by the prompt builder. The textual representation includes IDs so
    the model can cite the same items it saw visually.
    """
    data = {
        "metadata": record.meta,
        "mode": record.mode,
        "sections": [
            {
                "id": s.anchor,
                "number": s.number,
                "heading": s.heading,
                "level": s.level,
                "text": s.text,
                "equation_ids": s.eq_ids,
                "figure_ids": s.fig_ids,
                "table_ids": s.tab_ids,
                "footnotes": s.footnotes,
            }
            for s in record.sections
        ],
        "equations": [
            {k: v for k, v in item.items() if k not in {"image_bytes", "svg"}}
            for item in record.equations
        ],
        "figures": [
            {k: v for k, v in item.items() if k not in {"image_bytes", "svg"}}
            for item in record.figures
        ],
        "tables": record.tables,
        "algorithms": record.algorithms,
        "theorems": record.theorems,
        "references": record.references,
        "extraction_warnings": record.warnings,
    }
    context = json.dumps(data, ensure_ascii=False, default=str, separators=(",", ":"))
    prepared = PreparedSource(
        context=context,
        selected_anchors=[s.anchor for s in record.sections],
        chars=len(context),
        mode=record.mode,
        gated_figures=list(record.figures),
    )
    trace.log(
        "source", "complete_paper", "ok", chars=len(context),
        sections=len(record.sections), figures=len(record.figures),
        tables=len(record.tables), equations=len(record.equations),
    )
    return prepared
