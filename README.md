# Assignment 4 - Kazakh LLM Experiment

## Current stage - report and reproducible analysis

The report is `Assignment4_Nurbekova_Kadirbay_Kairkulova.docx`. Numerical tables,
three figures, the final 600-response dataset, statistical outputs and 30 error
cases are in `results/final_analysis/`.

Install the pinned analysis dependencies with Python 3.12 and reproduce the report.

```powershell
python -m pip install -r requirements.txt
python scripts/analyze_results.py --bert
python scripts/build_report.py
```

The first BERTScore execution downloads public multilingual BERT weights and
requires internet access. Later runs may use the saved `bertscore_120.json` with
`python scripts/analyze_results.py`; the source translation hash is checked.

Four evaluations came from the Gemini API, sixteen from manual Gemini collection,
and 580 from Codex. Human candidate confirmation was reported by the study team.
The 150-response labels were transcribed from their statement of identical errors
and carry `USER_REPORTED_AGREEMENT`. Original independent annotations were not
supplied. Perfect concordance values describe that statement and cannot establish
independently observed blind reliability. The report documents these limitations.

`analysis_manifest.json` records input hashes, software versions, seeds and runtime.
All primary counts require candidate-level confirmation. The primary inference uses
the 160 open-ended prompts; the 40 translation prompts are analysed separately.
Repository publication, the `assignment-4` tag and an independent reproduction
record remain to be completed by the study team.

## Evaluation workflow

### Manual Gemini evaluation

The current manual packet is in `results/manual_gemini_judge/`. Prepare or refresh
the task list using the following command while the API runner is stopped.

```powershell
.\scripts\run_judge.ps1 -Action prepare-manual
```

Open the next `tasks/Bxxxx.txt` file. Paste its entire contents into a fresh Gemini
chat using the model and thinking mode actually available in your account. Each
file contains the Judge prompt, rubric, annotation guideline and one anonymous
prompt-response pair. Save the first output verbatim in `responses/Bxxxx.json`
or `.txt`, preserving an enclosing Markdown fence if present. Store the displayed
model and actual thinking mode, using `Unknown` when unavailable. Record the
timestamp with timezone and optional conversation URL in the matching row of
`metadata.csv`. Set `raw_file` to the filename inside `responses/`.

Example timestamp is `2026-11-08T19:00:00+05:00`. For a repeated technical attempt,
also fill `technical_retry_reason`. Save invalid/aborted outputs and their metadata
before another attempt. Each blind ID permits at most three attempts in total
across the current 16k API evaluation revision and manual collection. Earlier
4096-token evaluation failures remain separately archived. The original response
text, model scores or error spans must not be edited to make JSON pass validation.

Import saved evaluations and refresh the combined export.

```powershell
.\scripts\run_judge.ps1 -Action import-manual
```

`combined_judge_600.jsonl` contains all 600 blind IDs with actual API/manual methods
and saved evaluation status. `progress.json` counts completed and remaining work.
`manual_imports.jsonl` preserves output bytes and collection metadata. Imported
attempts cannot be overwritten. Invalid JSON/schema output is logged for review.
`candidate_errors_for_review.jsonl` contains candidates requiring human verification.

`remaining_tasks.csv` is a refreshed pending list. `metadata.csv` is the working
collection log and is preserved by repeated preparation. Append rows for technical
retries with the next attempt number and a distinct raw filename. API/manual overlap
is rejected. The packet is read from blind inputs only. PRIVATE mappings stay local.

The Gemini web interface may expose different models, thinking modes, system
instructions or tool controls from the API. Record observed settings and describe
the collection-mode deviation in the report. The manual record does not assert the
API model version or output-token setting. Use a fresh independent chat per task
and disable available web/search/tools controls. Independent human annotators work
from their separate 150-response input before viewing these Judge suggestions.

The completed workbook supplied on 2026-11-08 is imported into
`results/selected200_analysis/`. Its source copy and import manifest preserve the
input. Each response is stored verbatim with its SHA-256 and frozen-rule word
count. Each source group has 200 records. Exact model versions and collection
settings are UNVERIFIED. Dates are missing for 541 responses, recorded in QC.

Prepared files in that directory include the following.

- `combined_600.csv` contains all responses and source metadata.
- `judge_input_blind.jsonl` contains shuffled anonymous evaluation inputs.
- `judge_mapping_PRIVATE.csv` maps blind IDs to source groups locally.
- `human_validation_150_blind.csv` supplies independent annotation inputs with
  50 responses per group, stratified by subset/task category, seed 20261030.
- `human_150_mapping_PRIVATE.csv` maps the independent sample locally.
- `translation_120.csv` contains 40 translation prompts across the three groups,
  with original English and reference Kazakh from the prompt dataset.

Keep PRIVATE mappings away from the Judge and independent annotator. Save human
annotations in a separate working copy of the blank template. Independently
annotate the 150-response sample before viewing Judge suggestions. Every Judge
primary-error candidate must also be manually verified before final counting.

Check Judge inputs offline in PowerShell.

```powershell
.\scripts\run_judge.ps1
```

Set `GEMINI_API_KEY` locally, then evaluate the first response.

```powershell
.\scripts\run_judge.ps1 -Execute -Limit 1
```

Continue evaluation after inspecting the first result.

```powershell
.\scripts\run_judge.ps1 -Execute
```

The wrapper finds local Python or the bundled runtime. The direct Python entry
point is `scripts/judge_responses.py`, with flags `--execute` and `--limit 1`.
Judge now uses `config/judge_settings_16k.json` with a 16384-token output limit
and high thinking. This revision follows the initial truncated B0001 evaluation
and is recorded in `docs/protocol_deviations.md`. Check the first revised result.
Truncated output pauses the batch for review.

Current results are written to `results/selected200_judge_16k/`. The initial
4096-token failure is retained in `results/selected200_judge/`.

- `attempts.jsonl` preserves request starts, finishes and raw HTTP bytes as base64.
- `judge_results.jsonl` contains all 600 IDs, their status and any validated JSON.
- `candidate_errors_for_review.jsonl` contains proposed errors for human review.
- `manifest.json` records input, configuration, guideline and code hashes.

Rate limits and exhausted quota pause the batch. Start the same command after
quota recovery. Completed evaluations are skipped. Interrupted requests are
UNKNOWN and require reconciliation. Invalid or truncated JSON is saved for
review. Input/configuration changes block resumption. A process lock protects
concurrent writes. The entire annotation guideline and rubric accompany each
request. Model group labels and PRIVATE mappings stay outside the payload.

Reproduce preparation with the source workbook and run offline tests.

```powershell
python scripts/prepare_analysis.py "C:\Users\nurai\Downloads\Selected_200_Prompts_Tracker_with_Gemini (1).xlsx"
python -m unittest discover -s scripts -p "test_*.py"
```

Repeated import verifies hashes and preserves prepared files. Import of the
completed tracker blocks further selected200 generation in the generation CLI.
The following sections document the earlier collection workflow.

## Current collection plan: Selected 200, Run A

The `selected200` collection profile uses the 200 prompts selected in the supplied
tracker, one response per prompt from each of three conditions: 600 planned
responses. Gemini runs through the API; GPT and Claude responses will be supplied
manually. This revised design differs from the original Protocol Freeze. See
`docs/protocol_deviations.md`. No random selection or exact identity of manually
collected models is assumed without evidence.

Files:

- `data/selected_200_prompts.csv`: selected rows, checked against original text.
- `config/selected_200_settings.json`: revised settings; Gemini high thinking,
  8192 output tokens. This does not guarantee completion for every response.
- `data/manual_selected200.csv`: 400 empty manual response slots.
- `results/selected200/`: new API journal, manifest and result exports.
- `scripts/generate_responses.py`: default Gemini-only runner.
- `scripts/manual_responses.py`: manual-response template and merge utility.

## Check and run

Python 3.10+; standard library only. In Windows PowerShell:

```powershell
py -3 scripts/generate_responses.py
py -3 -m unittest discover -s scripts -p "test_generate_responses.py"
```

Set `GEMINI_API_KEY` locally; never commit it or send it in chat. After deciding to
start the revised study, collect one response first:

```powershell
py -3 scripts/generate_responses.py --execute --limit 1
```

Check `provider_status` and `raw_response` in
`results/selected200/responses_raw.csv`. Then continue the remaining selected
Gemini slots using the same directory:

```powershell
py -3 scripts/generate_responses.py --execute
```

Daily quota exhaustion pauses the batch. Run the command again after quota resets;
there is no background scheduler. Valid HTTP responses, including empty, refused
or truncated output, are retained without quality-based regeneration. At most two
retries are permitted after an initial technical failure. Exhausted failures remain
in the journal. Interrupted requests are marked UNKNOWN and skipped without
resending; reconcile those slots separately using provider logs.

## Manual GPT and Claude responses

Fill `data/manual_selected200.csv` later. Keep each slot's `run_id`, `Prompt_ID`,
`model_key`, `run_number`, and `prompt_text` unchanged. Use an independent new chat
and save the first response verbatim. Fill:

- `model_version_displayed`: actual visible label; do not invent an API snapshot.
- `collected_at`: ISO timestamp with timezone, e.g. `2026-11-03T15:00:00+05:00`.
- `raw_response`: exact response text, including line breaks.
- `collection_interface`, optional `conversation_url`, and actual `settings_notes`.
- `response_saved`: `yes` once recorded, including genuinely empty output.

A note such as ?Codex; default model? does not establish GPT-6 Astra identity.
Record unknown settings honestly and report differences from the frozen protocol.
Existing responses from the supplied tracker have not been imported.

After adding responses, while the API runner is stopped:

```powershell
py -3 scripts/manual_responses.py merge
```

This creates `results/selected200/responses_with_manual.csv` with all 600 slots.
Re-run after more responses arrive. Original API records remain untouched;
received/uncertain API slots cannot be overwritten by manual import. Failed API
status is preserved in `api_status_before_manual` when a manual response is added.

## Original frozen study retained

The original design is 500 prompts x 3 models x 3 independent repeats = 4500
planned outputs. It is not completed by the selected-200 single-run study.

- Dataset: `data/prompts_500_v1.0.csv`.
- SHA-256: `bb8303cf296bcfb0e418166d551a8a5e2790798bd5e3c7fdb7e7b5b22f4126ec`.
- Settings: `config/generation_settings.json`.
- Original logs: `results/generation/`.
- Original manual template: `data/manual_responses.csv`.

Inspect the old plan without API calls:

```powershell
py -3 scripts/validate_prompts.py
py -3 scripts/generate_responses.py --profile frozen500
```

To merge old manual data explicitly:

```powershell
py -3 scripts/manual_responses.py merge --profile frozen500
```

Do not mix old outputs with the revised collection silently. The API runner keeps
requested model IDs separate from provider-reported versions. CSV is a derived
export; `attempts.jsonl` preserves attempts and unmodified HTTP bytes as base64.
The initial manifest is retained; maintenance-only runner revisions are logged
separately. Frozen settings and dataset hash changes block resumption.

## Evaluation and reproducibility

Judge prompt/rubric: `config/judge_prompt.txt`, `config/judge_rubric.json`.
Current Judge: Gemini 3.6 Flash; self-evaluation bias is a documented limitation.
Annotation rules: `docs/annotation_guideline.md`; retry policy:
`docs/retry_policy.md`; word count: `scripts/word_count.py`.

Primary error categories: Grammatical, Morphological, Lexical. Every distinct span
has at most one primary category; supplementary labels do not add primary errors.
Save raw responses without corrections. Judge and analysis requests are not run
by these collection scripts. No results or statistical claims are fabricated.

Record the actual Moodle upload timestamp and frozen commit in
`docs/freeze_record.txt`. Later changes belong in the protocol deviations. Report
model identity, collection mode, timestamps, failures, dataset selection, and the
absence of three-run variability in the revised single-run study.
