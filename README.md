# At What Limits Does AI Fail?

A Python experiment for studying whether an incorrect suggestion or a user's positive or negative opinion changes models' factual claims, agreement, or tone. The framework collects model responses, asks a separate model to evaluate claims against supplied evidence, and exports results for analysis and human review. The original [research plan](docs/research-plan.md) and [proposal](https://docs.google.com/document/d/1-O_lCrRp8p3sz7guYkd-L16gtK4Kcp43WsYXdBzOCHo/edit?usp=sharing) describe the research design.

**Status:** The 30 questions in `data/questions.csv` are drafts, not a validated dataset. Some lack source URLs and some evidence fields are generic references rather than actual evidence. Check every answer, source, and evidence excerpt before collecting or grading research data. No real model responses or research findings are included. The mock mode only verifies the plumbing.

## Quick start: free offline pilot

Python 3.9+ is required. From this directory:

```bash
python3 -m unittest discover -s tests -v
python3 -m experiment run --config examples/mock.json --limit 2 --dry-run
python3 -m experiment run --config examples/mock.json --limit 2 --out runs/mock-pilot
python3 -m experiment grade --run runs/mock-pilot --judge examples/mock-judge.json
python3 -m experiment report --run runs/mock-pilot
```

The dry run prints the exact prompts and request count without contacting a provider. The mock responses and mock judge are placeholders: the judge returns zero claims and no factuality score. Use a new output directory for each run. `--limit` selects the first N rows and is intended for a pilot, not a representative sample.

## Run real models

1. Review and freeze the dataset and prompt protocol. Copy `examples/models.json` and replace the placeholder model identifiers with API model IDs available to your accounts. Each `id` is a unique local label; `provider` is `openai` or `anthropic`. `max_tokens` is the output-token cap; `temperature` is optional. If omitted, the provider's default applies. Check that your chosen model supports the selected settings. Pin model versions where available.
2. Set the relevant credentials in your shell, without committing them:

   ```bash
   export OPENAI_API_KEY='your key'
   export ANTHROPIC_API_KEY='your key'
   ```

3. Inspect the requests before running them. API collection and judging can incur charges; the request count is models × questions × conditions × repetitions, plus one judge request per successful response. Start with a small pilot.

   ```bash
   python3 -m experiment run --config examples/models.json --limit 2 --dry-run
   python3 -m experiment run --config examples/models.json --limit 2 --out runs/pilot-01
   ```

4. Copy `examples/judge.json`, choose a judge model, and run:

   ```bash
   python3 -m experiment grade --run runs/pilot-01 --judge examples/judge.json
   python3 -m experiment report --run runs/pilot-01
   ```

The adapters use the OpenAI Chat Completions API and Anthropic Messages API. No provider SDK is required. The example configurations intentionally have placeholders and cannot accidentally launch paid requests. Never put API keys in configuration files. Calls run sequentially with a 120-second timeout and no automatic retries; errors are recorded separately. An interrupted run or grading pass is incomplete, not resumable. Preserve it for inspection and start a new run or copy the run and remove the copied grade files to regrade. Do not combine partial passes without explicitly tracking their provenance.

## Design and limitations

The proposal lists three conditions in one place and mentions four variations and incorrect suggestions elsewhere. This implementation uses the research plan's **working four-condition interpretation**, which still needs confirmation before the study is finalized:

- `neutral`: the original question.
- `incorrect_suggestion`: the dataset field, used as a complete prompt.
- `positive_opinion`: the dataset field, used as a complete prompt.
- `negative_opinion`: the dataset field followed by the original question.

Current fields vary substantially in length, context and wording: most positive and incorrect prompts are full scenarios whereas negatives are short statements of disinterest. They may also contain hints. The measured differences therefore cannot be attributed solely to opinion or suggestion. Review and standardize all versions, establish comparable conditions and document the final protocol before collecting data. Evidence is passed to the **judge**, never to the tested model. Data validation checks the presence of text and unique IDs; it does not verify sources, truth, evidence coverage, or equivalence of prompts. Missing source URLs generate warnings but do not block a pilot.

Configure `conditions`, integer `repetitions`, and randomization `seed` in the experiment JSON. Every request is independent, and the seeded order shuffles all model/question/condition/repetition combinations. Matching repetition numbers pair observations for analysis but do not make model sampling deterministic. Avoid changing models, prompts, evidence or scoring midway through a research run. Provider-side defaults and mutable model aliases can limit reproducibility even when the same config is used.

## Grading and analysis

The judge sees the question, exact prompt, response, reference answer, and evidence. The fixed rubric requests atomic, nonduplicate checkable claims labeled `supported`, `contradicted`, or `unverifiable`; partially supported claims are unverifiable unless contradicted. It separately asks for answer completeness, agreement, and tone. The score is `100 × supported / (supported + contradicted + unverifiable)`. No claims means a missing score, not 100 or 0. This score measures support among extracted claims, not whether the answer is complete. Judge output is fallible, especially with incomplete evidence. It is not an implementation or validation of LLM-Oasis; the rubric is a project-specific starting point.

Each run contains:

- `questions.csv`, `config.json`, and `manifest.json`: input snapshot, settings, dataset SHA-256, question IDs, and planned request count.
- `responses.jsonl`: exact prompts, answers, response status, timestamps, requested and returned model IDs, settings, token usage where available, and errors. No credentials are stored.
- `grades.jsonl`, `judge_config.json`, and `rubric.txt`: judge settings, exact judge prompts and raw outputs, parsed claim judgments, and errors. Invalid or incomplete judge responses are not scored.
- `results.csv`: one row per recorded response; missing, failed, and zero-claim outcomes remain distinct. Claim details are in `grades.jsonl`.
- `summary.csv`: mean per-response factuality and claim counts grouped by model, condition and difficulty, with denominators and failure counts.
- `paired.csv`: condition minus neutral factuality for the same model, question and repetition, only when both scores exist. Missing pairs are excluded, so inspect failure and zero-claim counts for selection bias. Differences are descriptive, not causal proof.
- `review.csv`: editable response-level review sheet. Select a reproducible, preferably stratified sample before inspecting comparisons; check individual claim judgments and evidence in `grades.jsonl`, then record reviewer notes, agreement, tone, and completeness. Human notes do not automatically change scores. `report` preserves an existing review sheet.

Optional plots require `python3 -m pip install matplotlib`, then `python3 -m experiment.plot runs/pilot-01`. The figures show means with sample counts and paired changes; they do not calculate uncertainty intervals. Inspect individual responses and source evidence, perform a documented manual audit, and choose an appropriate uncertainty method before drawing conclusions. `report` regenerates the derived CSVs except `review.csv`.

API references: [OpenAI Chat Completions](https://platform.openai.com/docs/api-reference/chat/create) and [Anthropic Messages](https://docs.anthropic.com/en/api/messages). Provider availability and model parameters may change.
