"""Separate selected-200 Run A plan; never overwrites the frozen 500-prompt study."""
import csv
import hashlib
import json
from pathlib import Path
from generation_config import load_settings

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / 'config/selected_200_settings.json'


def load_selected_plan():
    config = load_settings(SETTINGS)
    source = ROOT / config['selection_file']
    if hashlib.sha256(source.read_bytes()).hexdigest() != config['selection_sha256']:
        raise ValueError('Selected dataset hash mismatch')
    with source.open(encoding='utf-8-sig', newline='') as f:
        prompts = list(csv.DictReader(f))
    with (ROOT / 'data/prompts_500_v1.0.csv').open(encoding='utf-8-sig', newline='') as f:
        original = {p['Prompt_ID']: p for p in csv.DictReader(f)}
    if len(prompts) != 200 or len({p['Prompt_ID'] for p in prompts}) != 200:
        raise ValueError('Expected exactly 200 distinct selected prompts')
    plan = []
    for prompt in prompts:
        if prompt != original.get(prompt['Prompt_ID']):
            raise ValueError('Selected prompt differs from original dataset')
        for model in config['test_models']:
            plan.append(dict(run_id=f"S200_{prompt['Prompt_ID']}_{model['model_key']}_A",
                             run_number=1, prompt=prompt, model=model))
    if config['final_runs_per_prompt_model'] != 1 or len(plan) != 600 or config['expected_total_responses'] != 600:
        raise ValueError('Selected-200 Run A requires 600 planned responses')
    return plan
