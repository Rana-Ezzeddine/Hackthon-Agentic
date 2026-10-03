# Paper to Playground — Step 2 scaffold

This is **not yet a hackathon submission**. It adds a source-grounded planning
call to the Step 1 CLI and trace. The page is explicitly marked as a planning
preview. Later steps replace `scaffold_page()` with generated calculations,
controls, visuals, and real checks.

## Run

Requires Python 3.11 and an **OpenRouter-issued** API key. Set it in your shell;
never put it in `case.json`, the source code, or a commit.

```bash
python -m pip install -r requirements.txt
export OPENROUTER_API_KEY='your-key-here'
python agent.py --input case.example.json --output out --model deepseek/deepseek-v4.1-flash
```

Inspect `out/plan.json`, `out/index.html`, and `out/trace.jsonl`. The supplied
case is an explicitly **synthetic integration fixture**, not a paper excerpt or
the example input/output pair required for final submission. The program uses
the exact `--model` value; the shown DeepSeek slug is only a development example.

## Input contract pending clarification

The brief calls for five required string fields but names only `source_url`,
`focus`, and `audience`. It also refers to excerpts, while assessment network
access is limited to OpenRouter. This step provisionally reads an `excerpt`
field and preserves other JSON fields. Confirm the actual field name and source
delivery method with the instructor before final submission.

## Next steps

1. Generate calculations and generic visual components from the validated plan.
2. Add numerical and interaction checks with targeted repair.
3. Add total time/request/token guards and account for failed calls.
