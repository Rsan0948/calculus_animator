# Slide Review Workflow

## 1) Generate before/after audit + training pairs

```bash
cd "/Users/rubensanchez/Desktop/Personal Stuff/calculus_animator"
python tools/slide_quality_pipeline.py
```

Outputs:
- `reports/slide_quality_before_after.json`
- `reports/slide_quality_before_after.md`
- `training/slide_quality_pairs.jsonl`

## 2) (Optional) Ask local Ollama for alternative proposals

Start Ollama locally, then run:

```bash
cd "/Users/rubensanchez/Desktop/Personal Stuff/calculus_animator"
python tools/ollama_slide_reviewer.py --model qwen2.5:14b
```

Output:
- `reports/ollama_slide_proposals.json`

## 3) Dry-run prompt inspection (no model calls)

```bash
python tools/ollama_slide_reviewer.py --dry-run --limit 3
```

## Notes

- The app runtime slide highlights now use the informative highlighter in `core/slide_highlighting.py`.
- Keep highlights concise but educationally sufficient:
  - max 5 items
  - max 210 chars per item
  - max 620 chars total
