# Research plan

This is a working interpretation of the [original proposal](https://docs.google.com/document/d/1-O_lCrRp8p3sz7guYkd-L16gtK4Kcp43WsYXdBzOCHo/edit?usp=sharing), reviewed October 21, 2026. Proposed clarifications below are not decisions already made in that document.

## Objective

Measure whether user framing changes factual content, while distinguishing factual errors from changes in conversational style. The two research questions cover incorrect-answer suggestions and positive/negative opinions.

## Dataset

The current dataset contains 30 unique questions: 6 easy (20%), 9 medium (30%), and 15 hard (50%). Five questions cover each of the six existing topic areas. Difficulty follows the [dataset guide](../data/README.md): easy tasks require direct recall or one simple operation; medium tasks require a short application or conceptual distinction; hard tasks combine several operations, assumptions, or conditional interpretations. These are design labels, not measured model failure rates.

Each row includes a neutral question, reference answer with essential reasoning, source URL, evidence summary, and three full prompt variations. Quantitative scenarios are explicitly hypothetical, with all needed numerical inputs specified. The sources support the underlying facts or methods; scenario answers are derived rather than presented as reported observations.

## Prompt conditions

The current wide-format CSV stores four conditions per question: the neutral question and complete incorrect-suggestion, positive-opinion, and negative-opinion prompts. All versions use the same scenario and requested task. Opinion comparisons and incorrect-suggestion comparisons each use the neutral control. Send one prompt at a time without supplying reference answers or evidence to the tested model.

## Experiment framework

Planned Python modules:

- Dataset loading and validation.
- Fixed prompt templates for each condition.
- Model adapters for selected APIs or supported interfaces.
- Experiment controller and response storage.
- Evidence-based grading with a fixed rubric.
- CSV analysis and plots using pandas and plotting tools.

Record question ID, condition, exact prompt, model/provider, returned model version where available, sampling settings, run/repetition ID, timestamps, response, and errors. Keep collection failures separate from model factuality scores. Model selection, settings, and repetition count remain open.

## Factuality evaluation

The grader receives the question, response, reference answer, and evidence. It extracts checkable factual claims and labels each supported, contradicted, or unverifiable. Explore an LLM evaluator with simple rules where appropriate and manually audit a sample.

The proposal defines a 0–100 score from the proportion of evaluated claims supported by evidence. A candidate operational definition is:

`100 * supported / (supported + contradicted + unverifiable)`

This denominator and claim extraction rules must be finalized before evaluation. For zero checkable claims, report the score as missing and report the count separately; do not automatically award 100. Track contradicted and unverifiable counts/rates alongside the aggregate score. Specify how abstentions, omitted answers, duplicate claims, and partially supported claims are treated. A supported-claims score alone does not measure answer completeness.

Keep sentiment, tone, agreement, and changes in conclusions separate from factuality labels. Manual review should distinguish stylistic accommodation from factual changes. Decide the review sample and rubric before inspecting comparative results.

## Analysis

Compare factuality across models, conditions, and difficulty levels. Make bar charts of average factuality and charts of changes relative to neutral. Pair comparisons by question when possible, so differences in question difficulty do not drive condition comparisons. Review representative responses for agreement, conclusion changes, tone, and evidence emphasis. Any uncertainty estimates and repeated-run design remain to be specified.

## Open decisions before data collection

1. Pilot the difficulty labels and review prompt framing before freezing the dataset.
2. Select models, API settings, budget, and repetitions.
3. Review the curated questions and preserve source evidence for the final dataset version.
4. Freeze prompt templates and the scoring rubric.
5. Choose the evaluator and manual-review procedure.
6. Define treatment of no-claim responses and answer completeness.

## Suggested sequence

Finalize the protocol; curate the dataset; run a small pilot; resolve grading and logging issues; freeze the protocol; collect responses; grade and manually audit; analyze and write the report. The proposal's target is a full or submittable result before November 1.

## References listed in the proposal

These references are retained as supplied in the source document; their contents have not been independently reviewed for this repository setup.

- Sciré et al., “Truth or Mirage? Towards End-to-End Factuality Evaluation with LLM-Oasis.” https://direct.mit.edu/coli/article/52/1/1/133509/Truth-or-Mirage-Towards-End-To-End-Factuality
- Qazi et al., “Large Language Models Show Dunning-Kruger-like Effects in Multilingual Fact-Checking.” https://www.nature.com/articles/s41598-026-39046-w
