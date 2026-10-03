# Paper → Playground

Paper → Playground is a reusable Python agent that turns a paper URL and learning brief into one source-grounded, interactive HTML explanation for an engineering undergraduate. The generated page is self-contained and works offline; the agent, checks, trace, and fallback behavior are the submission.

## Team

Built by Nadine's Agentic AI Hackathon team.

## Run

Python 3.11 is required.

```bash
python -m pip install -r requirements.txt
export OPENROUTER_API_KEY='your-openrouter-key'
python agent.py --input case.json --output out --model MODEL_ID
```

The exact `MODEL_ID` argument is sent to OpenRouter. The key is read only from the environment and is never included in output or traces. Successful runs write exactly:

```text
out/index.html
out/trace.jsonl
```

`index.html` has embedded CSS, JavaScript, SVG, and any selected images. It has no CDN, remote font, runtime request, server, or build-step dependency.

## Input

`case.json` is UTF-8 JSON (maximum 2 MB) with three required non-empty strings:

- `source_url`: an HTTP(S) paper URL
- `focus`: the concept and required learning outcomes
- `audience`: assumed vocabulary, mathematics, and prerequisites

The agent recognizes common excerpt keys (`excerpt`, `paper_excerpt`, `source_excerpt`, `source_text`, and related names), nested source objects, excerpt lists, and long extra string fields. Short extra strings become metadata hints. See `case.example.json`.

## Architecture

1. Validate and normalize the case.
2. Prefer a supplied excerpt; otherwise try arXiv HTML, ar5iv, PDF, then generic HTML with strict timeout and size caps.
3. Parse the source into a normalized `PaperRecord` with metadata, sections, equations, figures, tables, and references.
4. Rank source sections against `focus`; `audience` never changes source selection.
5. Ask the selected OpenRouter model for one compact `PlaygroundSpec` containing explanation, deterministic compute code, visual code, controls, explorations, claims, and tests.
6. Compose one offline page from a governed component library, then run deterministic checks C0–C17. JavaScript is executed in isolated QuickJS contexts.
7. Send only failing fields and relevant source passages for up to two repairs. If failures remain, degrade optional visuals or relabel ungrounded claims visibly; mathematical failures are never hidden.

The budget is capped at 10 API requests, 30,000 completion tokens, and 540 seconds. One request and 1,000 tokens remain reserved. Normal runs use one generation call and zero or one repair. Every attempt, check, repair, failure, timing, and token count is recorded in `trace.jsonl`; prompts, source text, model output, credentials, and hidden reasoning are not.

## Failure and exit policy

- `0`: the page is usable (intro, executable compute, at least one view, and at least two working controls), even if non-critical failures are disclosed.
- `2`: only a static or unusable partial page could be produced.
- `1`: invalid input or an unrecoverable crash. A minimal error page is still written.

When paper retrieval or model generation is unavailable, the run fails soft with a clearly labeled illustrative fallback. It never presents fallback values as paper results.

## Development

```bash
python -m pip install -r requirements-dev.txt
pytest -q
```

Set `NO_FETCH=1` to exercise the OpenRouter-only network condition. Set `VISION=off` to disable figure attachments (vision gating is conservative and captions remain available).

## Repository map

`agent.py` owns orchestration and exit codes. `paperplay/` contains input, acquisition, parsing, selection, prompts, OpenRouter budgeting, specification handling, checks, degradation, trace, and rendering modules. `paperplay/design.py` governs the component catalog, variants, themes, required components, and ordering dependencies. `templates/page.html` is the component runtime rather than a prescribed page layout. `tests/` holds contract and parser fixtures; `cases/` contains practice cases; `examples/` contains one generated example pair.

## Governed visual composition

The model does not receive unrestricted HTML or CSS. It chooses an ordered composition from an allowlist of semantic components: hero, source strip, concept, symbols, paper figure, playground, explorations, limitation, evidence ledger, and appendix. Each has two or three layout variants. Six themes (`blueprint`, `aurora`, `graphite`, `parchment`, `circuit`, and `spectrum`) and three typography modes can be selected to suit the subject.

Governance guarantees exactly one hero, concept, playground, exploration group, limitation, and evidence ledger. The hero opens the page, evidence closes it, and explorations follow the executable playground. Unknown components, variants, colors, duplicates, and unsafe markup are rejected or normalized deterministically. If a model omits design direction, subject-aware defaults select an appropriate visual system without changing the scientific content.

## Credits and licenses

This project uses Requests (Apache-2.0), Beautiful Soup (MIT), certifi (MPL-2.0), QuickJS through its Python binding, and PyMuPDF/PyMuPDF4LLM (AGPL-3.0 or Artifex commercial license). No third-party source code is copied into the repository. Review the AGPL obligations before distributing a hosted or proprietary derivative.
