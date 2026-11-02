# Assignment 4 — Kazakh LLM Experiment

This starter repository is for the frozen experiment pipeline.

## Frozen design
- 500 prompts total
- 400 open-ended prompts
- 100 reference-based English→Kazakh translation prompts
- 3 model conditions
- Expected final outputs: 1,500

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

## Step 2 — create the 1,500-row raw-response template
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
Record:
- exact dataset SHA-256;
- repository URL;
- branch/tag/commit;
- exact models and versions;
- generation parameters;
- upload date/time.

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
