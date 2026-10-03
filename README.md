# Paper to Playground — paper preparation stage

The current CLI prepares the paper representation that a later model stage will receive. It makes **zero model calls** and does not select a relevant idea, create a plan, or generate an HTML playground.

## Run

Python 3.11 and the pinned packages in `requirements.txt` are required. The `--model` argument is retained for the final hackathon CLI interface but is not used at this stage. No OpenRouter key is needed.

```bash
python -m pip install -r requirements.txt
python agent.py --input case.example.json --output out --model deepseek/deepseek-v4.1-flash
```

The example case has the three available inputs: `source_url`, `focus`, and `audience`. The preparation process never uses `focus` or `audience` to filter the paper.

## What the CLI prepares

For arXiv URLs, it tries the full-text HTML first. It preserves the extracted text, headings, captions, tables, and every figure image. If HTML is unavailable or cannot be prepared, it falls back to the PDF. The PDF path extracts text and detected table rows from every page and renders every page so diagrams and other visual material are included.

`out/model_input.json` contains the unchanged three inputs, the full extracted paper text, and every figure or page image as a base64 JPEG data URL. Images are combined into numbered sheets only to bound the number of image parts in a future model request. `out/paper.txt` is a readable copy of the extracted text. `out/manifest.json` gives counts and indicates whether the images fit in one request. `out/trace.jsonl` records preparation events. No planning result or `index.html` is generated yet.

The case can be prepared only when the paper is retrievable from the execution environment. This remains an assessment integration constraint to verify.

## Reuse credits

PDF rendering, text, image, and table extraction use PyMuPDF. Image composition uses Pillow. HTTPS certificate roots use certifi.
