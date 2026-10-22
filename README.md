# At What Limits Does AI Fail?

Research project by David Ngerebara investigating how user framing affects large language models' factual accuracy, agreement behavior, and tone.

## Research questions

1. Does suggesting an incorrect answer influence a model's factual accuracy?
2. How do positive and negative user opinions affect factual claims, agreement, and tone?

## Planned study

- Curate 30–50 factual questions across topics, difficulty levels, and direct, multistep, and interpretation-based question types.
- Establish reference answers and supporting evidence before collecting responses.
- Compare neutral prompts, incorrect-answer suggestions, positive opinions, and negative opinions. The fourth condition is a proposed reconciliation of an inconsistency in the proposal; see the research plan.
- Build a modular Python framework with model adapters, reproducible run settings, response logging, and CSV analysis using pandas.
- Evaluate checkable claims as supported, contradicted, or unverifiable against the evidence, with a fixed rubric and manual review of a sample.
- Analyze tone and agreement separately from factual accuracy.

## Repository status

Initial research documentation only. Experiment code, model integrations, dataset curation, and grading have not been implemented. No model API calls or paid experiments have been run.

## Files

- [Research plan](docs/research-plan.md): interpretation of the proposal, evaluation plan, and unresolved decisions.
- [Dataset template](data/questions.csv): empty curation template; no experimental observations.

## Source and target

[Original project proposal](https://docs.google.com/document/d/1-O_lCrRp8p3sz7guYkd-L16gtK4Kcp43WsYXdBzOCHo/edit?usp=sharing), reviewed October 21, 2026. The proposal aims for a full or submittable research result before November 1.
