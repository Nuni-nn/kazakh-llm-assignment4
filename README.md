# Assignment 4 ? Kazakh LLM Experiment

## Current collection plan: Selected 200, Run A

The active `selected200` profile uses the 200 prompts selected in the supplied
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
