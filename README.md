# Paper to Playground

**Team members:** Rana Ezzeddine and Nadine Mcheik.

Paper to Playground turns a paper URL, a learning focus, and an audience into one self-contained interactive HTML lesson. The command-line entry point is `agent.py`.

## Setup and run

Use Python 3.11 or newer. From this repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Set `OPENROUTER_API_KEY` in your environment, then run:

```bash
python agent.py --input case.json --output out --model deepseek/deepseek-v4.1-flash
```

The input JSON requires `source_url`, `focus`, and `audience`. A successful run writes `out/index.html` and `out/trace.jsonl`. The HTML page embeds its CSS, JavaScript, and selected source visuals and works offline. The CLI exits nonzero when generation or required checks fail.

## Architecture

1. `paperplay/source.py` retrieves the paper, preferring arXiv full-text HTML and falling back to PDF. An arXiv abstract link is resolved to its versioned HTML link when available.
2. The readers parse sections, equations, tables, figures, references, and metadata. `paperplay/full_source.py` sends the complete parsed paper to the model without filtering it by the requested focus.
3. `paperplay/prompts.py` asks the model for a focus-guided lesson specification. `paperplay/render.py` applies it to the reusable template in `templates/`.
4. `paperplay/checks.py` tests the calculations, controls, guides, source anchors, page structure, and offline behavior. Failures can trigger a model repair; the trace records the outcome.

`examples/case.json` and `examples/index.html` are a checked-in synthetic input/output pair for viewing the offline page. Assessed outputs are generated afresh from the instructor's cases.

## Reuse credits

The implementation uses Requests for HTTP retrieval, Beautiful Soup for HTML parsing, certifi for HTTPS certificate roots, PyMuPDF and PyMuPDF4LLM for PDF extraction, and QuickJS for isolated JavaScript checks. The `templates/interaction_gallery.html` examples are design inspiration. No third-party application source code was copied into this repository.

To run the tests, install `requirements-dev.txt` and use `python -m pytest -q`.
