# Paper to Playground

Built by Nadine's Agentic AI Hackathon team.

This CLI turns a paper URL, a focus, and an audience into one source-grounded, self-contained interactive HTML page. The page is built by **editing a reusable focus-guided template**, not by asking the model to write a new document from scratch.

## Run

Install Python 3.11+ dependencies from `requirements.txt`, set `OPENROUTER_API_KEY`, and run:

```bash
python agent.py --input case.json --output out --model MODEL_ID
```

The input JSON needs `source_url`, `focus`, and `audience`. A successful run writes `out/index.html` and `out/trace.jsonl`. The generated page embeds its CSS, JavaScript, and selected source visuals; it makes no runtime network request.

## How HTML is generated

1. The agent retrieves the complete available paper, trying arXiv HTML first and PDF when necessary. It parses all sections, equations, tables, figures, references, and metadata. PDF pages are also rendered as images so non-text material remains available.
2. `paperplay/full_source.py` serializes the complete parsed record **without ranking or clipping it by focus**. Available figure/page images are attached to the model request with stable IDs. If a model endpoint rejects the images, the request fails rather than silently dropping them.
3. `paperplay/prompts.py` asks the model to inspect the whole representation, establish coverage of the requested focus, and return a `focus-guided-v2` JSON edit specification. The prompt includes the template contract and a brief overview of the interaction gallery. The gallery is inspiration, not an allowlist: the model may adapt or create a paper-specific visual.
4. `paperplay/render.py` applies those edits to `templates/focus_page.html` and its bundled `focus_style.css`. The model can produce any number of learning units, explanatory blocks, views, and guided explorations. The outer path remains focus → integrated learning units → synthesis → source and limits.
5. Each learning unit's calculation drives its controls, visual views, metrics, guided presets, and live notes. The guide is rendered **inside** the same fullscreen-capable studio as the visual. Rich explanatory HTML is sanitized; custom CSS is scoped to the unit; paper-specific compute and draw functions are checked before release.
6. Deterministic checks evaluate calculations, guided expectations, bindings, paper anchors, page structure, size, and offline behavior. The model can repair failed fields within the request budget. A failed or incomplete generation exits nonzero; it is not presented as a successful paper explanation.

The human-viewable visual design reference is `templates/interaction_gallery.html`. It demonstrates eight broad interaction ideas. It is deliberately **not** a fixed set of scientific templates; complex or unusual papers may need a different view produced within the same focus-guided page shell.

## Important limits

- The full paper is sent as available in the parsed record. A source that cannot be retrieved causes a clear failure. Extraction warnings are included in the model input.
- The generator does not know whether the configured OpenRouter model accepts image parts or how much complete-paper context it supports. Those capabilities must be verified with the selected model. It does not silently truncate source material or remove images on an unsupported-parameter retry.
- Source claims are checked against text anchors, and calculations are exercised, but automated checks cannot prove that an explanation is scientifically complete or pedagogically optimal. Review generated pages before submission.
- The model's custom visual is constrained to self-contained markup produced by a pure drawing function, with scoped CSS. The base page structure and interaction runtime remain reusable.

## Files

- `templates/focus_page.html`: production page structure and interaction runtime.
- `templates/focus_style.css`: visual system inlined into final HTML.
- `templates/interaction_gallery.html`: visual inspiration gallery.
- `paperplay/full_source.py`: complete-paper representation for the model.
- `paperplay/prompts.py`: current exact generation, repair, and parsing prompts.
- `paperplay/render.py`: applies model edits to the template.
- `paperplay/checks.py`: executable and structural release checks.

Tests: `python -m pytest -q` after installing `requirements-dev.txt`.
