# Paper to Playground — Desktop Codex handoff

## Objective and source of truth

Build a reusable Python 3.11 agent for the EECE503P / EECE798S six-hour hackathon. The authoritative brief is **Paper to Playground - Agentic Systems Hackathon.pdf**. Read it before making final design choices. This file summarizes the requirements and current implementation; it does not replace the brief.

The agent takes a focused paper input and learning brief, then autonomously makes one browser-ready interactive explanation for an engineering undergraduate. It must work for five hidden cases without changing code or manually editing generated pages. They run the frozen commit twice per case.

## Repository and local path

- GitHub: `Rana-Ezzeddine/Hackthon-Agentic` (private, default branch `main`).
- User's Mac path: `/Users/ranaezzeddine/Desktop/Hackthon-Agentic`.
- The cloud workspace cannot directly access that Mac path. Pull from `origin/main` in Desktop Codex; check `git status --short` first so local work is preserved.
- Never commit an API key or include one in generated HTML or traces.

## Required execution contract

```bash
python -m pip install -r requirements.txt
python agent.py --input case.json --output out --model MODEL_ID
```

- `agent.py` at repository root, Python 3.11, pinned dependencies in `requirements.txt`.
- `case.json` is UTF-8 JSON. The brief names `source_url`, `focus`, `audience`; `focus` states the concept and learning outcomes.
- All model calls must use the exact CLI `MODEL_ID` through `https://openrouter.ai/api/v1/chat/completions`, authenticated from `OPENROUTER_API_KEY`.
- User's development model is DeepSeek V4.1 Flash on OpenRouter, slug `deepseek/deepseek-v4.1-flash`. This is an example CLI value, never hard-code it. The instructor supplies an assessment key and model ID.
- Assessment limit per case: 10 minutes, at most 10 API requests including retries, at most 30,000 completion tokens. Track all calls, retries, elapsed time, and reported prompt/completion usage. Favor 2 normal calls plus targeted repair where feasible.
- Write `out/index.html`, one self-contained file with embedded CSS, JS, and visuals. It must work offline in Chromium when served locally; no CDN, remote image/font, build step, or page-embedded key.
- Write `out/trace.jsonl`, one JSON object per event with stage/action/result, per-call usage and time, checks, failures, and revisions. Never log credentials or hidden reasoning.
- Exit 0 only when a usable generated explanation satisfies the required checks; nonzero on failure. The current scaffold does **not yet** meet this final condition.
- Final repo needs README with team members, architecture, setup, reuse credits, and one real example input/output pair. Submit repo URL and full commit SHA before the six-hour session ends.

## Generated page checklist

1. Idea, why it matters, main symbols defined at audience level.
2. Readable, scientifically accurate visual explaining the mechanism.
3. At least two meaningful controls that update relevant visuals or calculations; numerical outputs are computed, not invented.
4. Two guided explorations: what to change, observe, and why; one limitation/assumption/misunderstanding.
5. Paper identity and relevant section/equation; supported claims distinguished from illustrative simplifications. Do not imply a toy demo reproduces experimental results.

Public practice cases: Attention Is All You Need §3.2.1 (small editable Q/K/V, scaling toggle, scores, normalized weights and output; check row sums and weighted sums) and Shannon, A Mathematical Theory of Communication §6 (probability distribution, outcome count, contributions and entropy in bits; check certainty=0, four equiprobable=2, zero probabilities). They are examples, not special cases to hard-code. Hidden cases are similarly focused mechanisms or quantitative relationships with small inputs.

## Rubric

Scientific accuracy/fidelity 25; teaching clarity 20; visual explanation 15; working interaction 15; autonomous generation/checks 10; token efficiency 10; latency 5. Efficiency is awarded only if quality reaches at least 50/85. Token points are `10*Tmin/T`, latency points `5*Lmin/L`, compared with qualifying runs on each hidden case. Final score averages ten runs. Prioritize quality, correctness, and repeatability before optimizing tokens.

## Important input-contract ambiguity

The PDF says **five required string fields** but lists only three. It says hidden cases contain an excerpt, yet assessment network access is limited to OpenRouter. We still need the instructor's complete sample `case.json` and explicit excerpt delivery method. Do not assume arXiv or other source URLs can be fetched during assessment. Current Step 2 code provisionally expects an `excerpt` string field and fails clearly if missing. Change this after seeing the actual input contract. `source_url` is for attribution unless fetching is expressly possible. The included `case.example.json` is a synthetic integration fixture, not a real paper excerpt or final showcase.

## Current implementation (Step 2 scaffold, not submission-ready)

- `agent.py`: exact CLI parsing, input validation, provisional `excerpt` requirement, call to planning model, plan validation, `out/plan.json`, planning-preview `out/index.html`, JSONL events.
- `paperplay/openrouter.py`: Python-standard-library OpenRouter POST; exact CLI model; key from environment; API-reported usage and call duration; sanitized errors. No retry or global budget yet.
- `paperplay/prompts.py`: asks for a compact source-grounded plan in JSON and treats the excerpt as untrusted data.
- `paperplay/schema.py`: validates source evidence is an exact excerpt span, concept, at least two controls, supported visual type, exactly two explorations, limitation, at least two planned checks.
- `tests/test_planning.py`: mock integration test for plan/usage/trace and missing-excerpt failure; no paid API call. Run `python3 -m unittest discover -s tests -v`.
- `requirements.txt`: no dependencies yet; all current runtime code uses the Python standard library.
- `README.md`: current Step 2 usage and warnings.

Known limitations: `index.html` is a planning preview with no calculations/visual controls; `plan.json` is intermediate. Planned check descriptions are not executed. No full source fidelity review, repair loop, overall deadline, request cap, or final output validation exists yet. A successful Step 2 run currently exits 0 even though it is not a finished explanation; fix that before submission.

## Recommended architecture to finish

Keep one agent loop and stable interfaces:

1. **Source/input adapter:** load confirmed excerpt and focused brief. Keep source data separate from instructions. Validate source evidence against excerpt.
2. **Mechanism planner:** model returns validated structured spec: symbols, controls, causal or mathematical steps, visual semantics, two explorations, source location, limitation, and checkable expectations.
3. **Logic generator:** model returns a small pure `compute(inputs)` JS function with intermediate values, result, and visual data. The same values drive both displayed numbers and the visual. Avoid asking the model to regenerate CSS/layout every case.
4. **Fixed single-file page shell:** own HTML/CSS, input events, labels, source box, guided-exploration UI, inline SVG drawing. Generic bar/curve/matrix/process renderers can cover many cases; provide a constrained custom path if needed for unseen mechanisms.
5. **Checks:** validate schema and source spans; execute `compute` at default, guidance, and edge inputs; check finite values, invariants, and meaningful response to each control. Derive independent expected values where the brief/source gives them. Test browser interactions and visual readability during development. A DOM change by itself does not prove correctness.
6. **Targeted repair:** send exact failures and only the faulty component back to the same supplied model, then rerun checks. Log actual checks and revisions. Cap calls, tokens, and time; preserve a usable page where possible, but never misreport a failed check.

The model should be free to express unseen mechanisms; avoid a rigid hard-coded entropy/attention solution. The shell and validation code are fixed across cases.

## Reuse decisions and credits

- **PaperVoyager** (`arxiv.org/abs/2603.22999`): use its published *idea* of mechanism extraction → structured interaction plan → synthesis. Its public GitHub `LICENSE` currently says "License pending" and grants no code reuse. Do not copy code from it.
- **I-WebGenBench** (`github.com/vast88912-stack/I-WebGenBench`): MIT-licensed. Its `benchmark/runner/run_module_probe.py` enumerates visible controls, acts on them, and detects DOM changes in Chromium. Adapt this narrow idea/code for a development probe if useful; retain the copyright and MIT notice for copied code, and credit the source in README. Its React/Vite generator and `playwright install chromium` are unsuitable as required assessment runtime steps.
- Use standard library or pinned Python packages for HTTP, schema validation, and JavaScript execution as needed. Verify Python 3.11 installation without system packages. Build small generic inline SVG/CSS assets or use assets only with compatible license and offline embedding. Credit anything reused.

## Immediate next actions in Desktop Codex

1. Run `git status --short`, pull `origin/main` if local work is clean, and inspect this handoff and the PDF.
2. Run the existing mock tests. Do not paste an API key into chat or files; set `OPENROUTER_API_KEY` in the local environment for a live test when ready.
3. Confirm the instructor's exact input schema. Update the source adapter as soon as it is known.
4. Implement logic generation and the fixed interactive page shell, then executable checks and repair.
5. Test fresh outputs for both public papers and at least one unrelated synthetic mechanism; inspect in Chromium; compare numbers with independent calculations.
6. Update README with team members, architecture, setup, exact reuse credits, and a genuine example input/output. Freeze and submit the full commit SHA only after the end-to-end run passes.
