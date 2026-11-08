# Deviations from the Frozen Protocol

## Final evaluation and analysis evidence 2026 November 8

The completed evaluation comprises 4 Gemini API records, 16 manual Gemini records
and 580 Codex assistant reviews. The latter are labelled ASSISTANT_REVIEW and do
not claim Gemini provenance. The team reported that human review confirmed the
same candidate errors. Candidate-level confirmation records identify USER_REPORT
as their basis, with reviewer identity and actual review time unavailable.

At the team's explicit request, the 150-response human validation file was filled
from their report of identical errors. Its annotator_id is
USER_REPORTED_AGREEMENT and each row states that the original independent labels
were not supplied. Agreement, kappa and recall calculated from this transcription
describe asserted concordance and cannot independently demonstrate reliability or
measure false negatives. The sample has 50 responses per model but difficulty
counts of 35 Basic, 28 Intermediate, 51 Advanced and 36 Expert, so the actual
sampling implementation did not explicitly balance difficulty as the freeze
requested.

Analysis implementation choices were fixed during report preparation. The prompt
bootstrap uses 10000 samples with seed 20261030, with 2000 prompt-cluster samples
for correlation intervals. Wilcoxon uses the two-sided asymptotic method, discards
zero differences and uses average ranks for ties without continuity correction.
SacreBLEU uses the 13a tokenizer, ChrF uses character orders 1 through 6 and beta
2, and ROUGE uses Unicode word sequences with lowercase conversion and no
stemming. BERTScore uses multilingual cased BERT at layer 9 without IDF or baseline
rescaling. Full unmodified raw responses are scored, including commentary.
Metric signatures and environment versions are saved in final_analysis outputs.

The post hoc evaluator sensitivity analysis retains the 140 open-ended prompt
blocks whose three responses were all evaluated by Codex. It is descriptive
robustness evidence and does not eliminate common-evaluator bias. Instructor
approval of the evaluation changes is not documented in this workspace.

## Manual evaluation batch paused after B0020 — 2026-11-08

At the user's request, manual Gemini evaluation was paused after B0020. The merged
export contains four API evaluations and sixteen manual evaluations, twenty total.
Raw outputs, visible model/mode, chat URLs and capture timestamps are saved for
each manual record. B0008 was generated with the new tab's default low thinking
mode, verified in the menu after generation. This output is retained with its
actual mode recorded. Later submissions were checked for high thinking before
sending. This single mode difference must be disclosed in analysis limitations.
The user requested a pause with 580 evaluations remaining. No further evaluation
is scheduled in the background.

## First manual Judge record and validator correction — 2026-11-08

B0005 was evaluated in a fresh Gemini chat through the visible Gemini 3.6 Flash
selection with reasoning level Высокий. The first manual output is saved as
results/manual_gemini_judge/responses/B0005_attempt2.json with its chat URL and
capture timestamp. It is attempt 2 in the current evaluation revision, following
the initial API evaluation. No additional manual generation was requested.

Both the manual result and the initial API evaluation used JSON null for an
inapplicable suggested correction on a supplementary format issue. The validator
was overly strict in requiring a string in that field. It now accepts string or
null for suggested_correction while retaining the other schema checks. Saved
source JSON is preserved. Original API invalid status remains part of its history.
Validation-only runner maintenance is logged separately when the API runner resumes,
with its original manifest retained and experiment inputs/settings checked.

## Mixed API and manual Gemini Judge collection — 2026-11-08

The user chose to evaluate remaining responses manually in Gemini because API
quota and budget prevent completing all evaluations promptly through the API.
At packet preparation, four valid API evaluations (B0001-B0004) were retained.
B0005 had an invalid field type under the configured JSON schema. Its source API
output is retained, and a manual technical follow-up requires an explicit reason.
The remaining 596 tasks are supplied as individual anonymous text files, each
containing the configured Judge prompt, rubric and complete annotation guideline.

The final evaluation export distinguishes API from MANUAL_GEMINI and records
actual visible model/mode and timestamps for manual evaluations. Available web
interface settings may differ from the API. Such settings must be observed and
reported, and API model IDs/output-token limits must not be invented for manual
records. Use a fresh chat for each input. Save the first output verbatim including
technical failures. Output bytes, source hashes and collection metadata are retained.
Completed API evaluations are excluded from manual tasks and duplicate completed
API/manual evaluations require reconciliation. Invalid outputs are saved for review.
All primary-error candidates still require human verification. Independent human
annotation uses its separate blind input without access to Judge suggestions.

## Judge output budget revision — 2026-11-08

The initial B0001 evaluation with high thinking and 4096 output tokens ended
with MAX_TOKENS. Provider usage reported 3928 thinking tokens and 164 visible
output tokens. The visible output was incomplete and failed JSON validation.
The source HTTP response and failure remain in results/selected200_judge.

After the user requested resolution, the output budget was increased to 16384
in config/judge_settings_16k.json. The model, thinking level, rubric and annotation
guideline retain their configured values. A separate evaluation revision writes
to results/selected200_judge_16k and starts with B0001. This is a disclosed settings
revision after one failed evaluation, rather than an unlogged retry under the
initial settings. Initial and revised evaluations must be distinguished in the
report. The revised budget requires checking the first evaluation before scaling.

## Completed tracker import and evaluation preparation — 2026-11-08

The user supplied Selected_200_Prompts_Tracker_with_Gemini (1).xlsx and authorized
importing the responses and preparing evaluation code. All 600 source response
strings are preserved, grouped under the source labels GPT, Gemini and Claude.
These labels have unverified exact model identities and collection settings.
Date cells are missing for 141 GPT records, 200 Claude records and 200 Gemini
records. Existing Excel date values are retained as source values. Dates, API IDs
and settings were not inferred from planned generation configuration.

The source workbook and SHA-256 are archived in results/selected200_analysis.
Each response has a SHA-256 and word count from scripts/word_count.py. Blinded
judge IDs are shuffled with seed 20261030. The independent human sample uses the
same seed, 50 responses per source model group and proportional allocation across
subset/task-category strata. There is only Run A. No Judge results are included
in the independent annotation input. Private mappings are excluded from requests.

The evaluation runner supplies the existing Judge prompt, rubric and complete
annotation guideline on each request, using the configured Gemini model, high
thinking and 4096 output tokens. JSON MIME mode is requested. Technical retries
remain limited to two after the initial attempt. Rate-limit/quota responses pause
the batch. Malformed, truncated, refused or schema-invalid Judge output is saved
for review and pauses the batch. It is not automatically regenerated. All
primary-error candidates require human verification before final error counts.

## Selected-200 Run A profile — 2026-11-03

The user supplied Selected_200_Prompts_Tracker_with_Gemini.xlsx and requested code
changes, with responses to be supplied later. A separate selected200 profile follows
its 200 selected prompts and Run A sheets: 200 prompts x 3 models x 1 run = 600
planned outputs. Selection is supplied by the team, not asserted to be random or
unbiased. All selected prompt rows were checked against the original dataset.
The original 500-prompt, three-run profile and its records are retained separately.

For this revised profile Gemini uses high thinking with maxOutputTokens=8192,
instead of 2048, because the original logs showed thinking consuming most of the
budget and 15 of 17 received responses ending with MAX_TOKENS. This is a disclosed
post-observation change, not the original frozen configuration. The new limit
does not guarantee every response will be complete. No old output is regenerated,
removed or automatically mixed into this revised profile. Existing tracker
responses are not yet imported. GPT sheet notes such as 'Codex; default model'
do not establish the frozen GPT-6 Astra identity and must be verified or reported
as unverified when the actual responses are imported.

The reduced single-run study cannot supply three-run variability estimates and
cannot be described as completing the original 4500-output frozen experiment.
These differences and the selection procedure must be described in the report.

## Judge configuration replacement — 2026-11-02

The user supplied a replacement `config/generation_settings.json` after reporting
that the Protocol Freeze had been uploaded. The replacement changes the Judge
from Claude Opus 5.5 (adaptive thinking, medium effort) to Gemini 3.6 Flash
(high thinking level), with a 4,096-token output limit and tools disabled.
The tested-model identity remains hidden from the Judge.

Reason for the Judge replacement: not yet provided by the study team.
The team must supply the reason in the final report; this entry does not amend
the already uploaded Protocol Freeze or establish a Moodle upload timestamp.

Gemini is also a tested model, so possible self-evaluation bias must be reported
as a limitation and assessed through human validation. No Judge calls have been
made by the scripts prepared in this workspace.

The supplied file uses protocol label `A4_FINAL_SIMPLE` and a simplified schema.
The generation scripts translate that schema internally without changing the
supplied file. The tested models, generation settings, 500 prompts, three repeats
and 4,500 planned outputs remain as specified. Retry and word-count rules remain
in `docs/retry_policy.md` and `scripts/word_count.py`.

## Manual OpenAI/Claude collection and daily Gemini batches — 2026-11-02

The study team chose manual collection for GPT-6 Astra and Claude Sonnet 5.5
because OpenAI API credits were exhausted and Claude was already planned for
manual collection. Gemini remains on the API, collected in batches as daily quota
allows. No background scheduler is installed. The default runner now selects only
Gemini; the overall model/prompt/repeat plan remains 4,500 slots.

Manual responses must use independent fresh chats and unchanged prompt text.
Record the actual model label, interface, timestamp with timezone, and settings
that were actually available. Do not assert API settings or immutable model
versions that the chat interface does not expose. Differences in system prompts,
context, token limits, tools and reasoning controls may confound model comparisons
and must be reported. No manual response has been collected by this change.

Original failed API attempts remain in the journal. A manual response for a failed
OpenAI slot is an explicitly documented collection-mode deviation, not an erased
failure. The combined export preserves the preceding API status; received API
answers cannot be overwritten through the manual importer.

The interrupted Gemini request RUN0114 attempt 1 has no recorded response.
It is marked UNKNOWN in derived exports, without inventing a provider outcome or
altering the original journal. It is excluded from automatic re-submission pending
provider-log reconciliation. Other untouched slots may proceed.

Runner maintenance stops a batch on exhausted credits/daily quota and retains
unused retry budget. Existing exhausted failures remain terminal. The initial
manifest stays unchanged; runner code revisions are logged separately after
checking that the frozen experiment files are unchanged.
