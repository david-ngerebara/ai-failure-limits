# Question dataset

The dataset has **30 unique questions**, with the requested split:

| Difficulty | Questions | Share |
|---|---:|---:|
| easy | 6 | 20% |
| medium | 9 | 30% |
| hard | 15 | 50% |

There are five questions in each existing topic: space and astronomy; Earth science and environment; biology and health; physics and chemistry; computing and AI; and mathematics and statistics. The topic spellings in the CSV are retained from the original dataset.

## Difficulty rubric

- **Easy:** a familiar fact, a direct classification, or one simple calculation.
- **Medium:** a short application, two connected steps, or a conceptual distinction that must be explained.
- **Hard:** multiple dependent steps plus interpretation, such as converting units before applying a model, conditioning a probability, handling a phase-change constraint, distinguishing an aggregate result from within-group results, or designing evaluation under simultaneous time and group restrictions.

Length and specialist vocabulary alone do not define difficulty. These labels describe intended reasoning burden within this dataset; they do not establish that a particular model will fail. Calibrate them in a pilot before drawing conclusions about model capability. The set contains a mix of conceptual and quantitative tasks and therefore evaluates factual knowledge together with reasoning, not factual recall alone.

## Columns and prompt use

The original 11 columns are preserved:

`question_id`, `question`, `topic`, `difficulty`, `question_type`, `reference_answer`, `source_url`, `evidence_text`, `incorrect_suggestion`, `positive_opinion`, `negative_opinion`.

- `question` is the complete neutral prompt.
- Each of the last three columns is also a **complete prompt**, not text to append to the neutral question.
- Every version retains the same scenario, assumptions, and requested task. Only the framing sentence changes.
- Incorrect suggestions deliberately introduce a mistaken conclusion or method. They are experimental stimuli, not facts endorsed by the dataset.
- Positive and negative opinions express attitudes toward the same subject without providing an answer. Evaluate each against neutral separately, and compare them with each other.
- `reference_answer` includes essential results and reasoning. Equivalent correct wording and sensible rounding should be accepted. Final scoring rules still need to be frozen.
- Do not include `reference_answer`, `source_url`, or `evidence_text` in the tested model's prompt. Those are for grading and audit.

One row is one unique question. Four condition prompts across 30 rows give 120 requests per tested model per repetition if each condition is run once. Reuse a matched neutral response in both analyses only when model settings and run design are identical; do not count it twice as independent evidence.

## Sources and hypothetical data

Sources were consulted on November 15, 2026. Links point to the relevant source pages. Evidence summaries are paraphrases of the supporting principle, sometimes followed by a calculation from the question's stated assumptions. They are not verbatim source quotations.

Numerical scenarios, such as the comet orbit, genetic counts, circuit, catchment, and classifier, are hypothetical. They should not be attributed to NASA, USGS, or another source as actual measurements. Reference answers apply the cited methods to those invented inputs. A source supporting a method is not being represented as reporting the scenario's exact numeric result.

## Versioning

This revision replaces earlier questions while retaining the 30 row IDs and topic assignments. Record the repository commit together with question ID and condition in experiment results. Do not combine old and new responses by question ID alone. The raw master file originally supplied by the user is unchanged.
