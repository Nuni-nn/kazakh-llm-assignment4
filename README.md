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
