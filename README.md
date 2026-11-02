# Assignment 4 — Kazakh LLM Experiment

This starter repository is for the frozen experiment pipeline.

## Frozen design
- 500 prompts total
- 400 open-ended prompts
- 100 reference-based English→Kazakh translation prompts
- 3 model conditions
- 3 runs per prompt-model pair
- Expected final outputs: 4,500

## Important rule
Do **not** run the final 500-prompt experiment until:
1. the dataset has passed validation;
2. the exact model/version/settings are recorded;
3. the Protocol Freeze has been uploaded to Moodle;
4. the repository commit/hash used for the freeze is recorded.

## Step 1 — validate the dataset
```bash
python scripts/validate_prompts.py
```

Expected result: `PASS: Dataset is internally consistent.`

## Step 2 — create the 4,500-row raw-response template
```bash
python scripts/create_response_template.py
```

This creates:
`data/responses_raw_template.csv`

The raw model response must be stored exactly as received. Do not correct or delete unfavorable outputs.

## Step 3 — create the annotation template
```bash
python scripts/create_annotation_template.py
```

This creates:
`data/human_annotations_template.csv`

Primary categories:
- grammatical
- morphological
- lexical

Supplementary categories:
- orthographic
- script mixing
- code-switching
- calque
- politeness inconsistency
- hallucinated word
- factual error
- instruction-following error
- Other

## Before the Protocol Freeze is uploaded
Frozen dataset SHA-256:
`bb8303cf296bcfb0e418166d551a8a5e2790798bd5e3c7fdb7e7b5b22f4126ec`

Record:
- exact dataset SHA-256;
- repository URL;
- branch/tag/commit;
- exact models and versions;
- generation parameters;
- upload date/time.

Commit the frozen dataset and configuration files, then run `git log -1 --oneline`.
Enter the resulting commit hash in the Protocol Freeze before uploading it to Moodle.

## After the Freeze
Only then create the final generation scripts or run the models on the 500 frozen prompts.

## Reproducibility
Every reported number in Assignment 4 should be traceable to:
- Prompt_ID
- run_id
- model/version
- raw_response
- annotation
- evaluation script/output

## Frozen configuration files
- Dataset: `data/prompts_500_v1.0.csv`
- Generation settings: `config/generation_settings.json`
- Judge: `config/judge_prompt.txt` and `config/judge_rubric.json`
- Annotation rules: `docs/annotation_guideline.md`
- Retry policy: `docs/retry_policy.md`
- Word counting: `scripts/word_count.py`
- Protocol deviations: `docs/protocol_deviations.md` (current Judge: Gemini 3.6 Flash).

## Final generation (after Moodle Protocol Freeze upload)

The runner uses Python 3.10+ and the standard library; no packages are required.
It reads the frozen configuration without changing model IDs or sampling settings.
First check the plan offline (no API calls):

```powershell
py -3 scripts/validate_prompts.py
py -3 scripts/generate_responses.py
py -3 -m unittest discover -s scripts -p "test_generate_responses.py"
```

Set `OPENAI_API_KEY`, `GEMINI_API_KEY`, and `ANTHROPIC_API_KEY` in your local
environment. Keep keys outside the repository. The provider accounts must have
API access and billing for the exact frozen models. Then start the paid run:

```powershell
py -3 scripts/generate_responses.py --execute
```

The same command resumes remaining runs. To work in batches, add `--limit 30`;
this executes up to 30 remaining planned responses, including their permitted
technical retries, without changing the 4,500-response plan.

Outputs in `results/generation/`:

- `responses_raw.csv`: all 4,500 planned rows, including NOT_RUN and FAILED rows;
  repeat number, requested/reported model version, timestamp, request/response IDs,
  original visible response, provider status, and retry/failure information.
- `attempts.jsonl`: durable start/finish events, exact request payloads (no API keys),
  HTTP headers and unmodified response bytes encoded as base64, including errors.
- `manifest.json`: frozen file hashes, generation settings, Python/OS versions,
  creation timestamp and request timeout.

Every successful HTTP response is retained, including refusals, empty or truncated
answers. `RECEIVED` means an HTTP response was saved, not that it passed linguistic
or instruction checks. `RECEIVED_UNPARSED` preserves the response for inspection.
The exact version field contains only what the provider reports; it remains empty
if unavailable. Requested aliases are recorded separately and never presented as
verified immutable model snapshots.

Only transport errors, HTTP 408/429 and 5xx errors permit retries, at most two after
the initial attempt. Completed/failed runs are never automatically regenerated.
HTTP 400/401/403/404 stops the batch for inspection and retains the failed row.
Resume rejects changed frozen files or runner code. A process lock prevents two
runners from writing to the same output directory.

If execution ends between a request-start and request-finish event, resume stops:
the provider may already have generated/billed the response. Reconcile the request
against provider logs before continuing; do not delete the journal or start a new
output directory to bypass it. Keep the same output directory throughout the study.
The CSV is a derived export; the attempt journal is the source record.

Record the actual Moodle upload timestamp and frozen repository commit in
`docs/freeze_record.txt`; the runner does not invent or verify Moodle evidence.
No Judge requests or human annotations are performed by this generation script.

API references: [OpenAI Responses](https://developers.openai.com/api/docs/guides/text),
[Gemini thinking](https://ai.google.dev/gemini-api/docs/generate-content/thinking),
[Claude Messages](https://platform.claude.com/docs/en/api/messages/create).
