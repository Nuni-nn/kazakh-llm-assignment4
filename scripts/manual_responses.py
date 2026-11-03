"""Create manual-response template and merge supplied responses without editing API logs."""
import argparse
import csv
from datetime import datetime
from pathlib import Path
from generate_responses import ROOT, load_plan, read_events, export_csv

MANUAL_FIELDS = ['run_id', 'Prompt_ID', 'model_key', 'run_number', 'prompt_text',
                 'model_version_displayed', 'collected_at', 'raw_response', 'collection_interface',
                 'conversation_url', 'settings_notes', 'response_saved']


def template(path, plan=None):
    if path.exists():
        raise ValueError(f'Will not overwrite existing manual data: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=MANUAL_FIELDS)
        w.writeheader()
        for run in (load_plan() if plan is None else plan):
            if run['model']['model_key'] == 'gemini36_flash':
                continue
            w.writerow(dict(run_id=run['run_id'], Prompt_ID=run['prompt']['Prompt_ID'],
                model_key=run['model']['model_key'], run_number=run['run_number'],
                prompt_text=run['prompt']['Prompt_KK']))


def merge(source, directory, plan=None):
    plan = load_plan() if plan is None else plan
    events = read_events(directory / 'attempts.jsonl')
    # Separate export: original journal and API CSV remain untouched.
    base = directory / 'responses_with_manual.csv'
    export_csv(plan, events, base)
    with base.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames + ['collection_method', 'api_status_before_manual',
                                      'conversation_url', 'settings_notes']
        rows = {r['run_id']: r for r in reader}
    seen = set()
    with source.open(encoding='utf-8-sig', newline='') as f:
        for item in csv.DictReader(f):
            if not item.get('response_saved', '').strip():
                if item.get('raw_response'):
                    raise ValueError('Response text present without response_saved=yes')
                continue
            if item['response_saved'].strip().lower() != 'yes':
                raise ValueError('Use response_saved=yes for a recorded response (including empty output).')
            identity = item['run_id']
            if identity in seen or identity not in rows:
                raise ValueError(f'Duplicate/unknown run: {identity}')
            seen.add(identity)
            row = rows[identity]
            if row['model_key'] == 'gemini36_flash':
                raise ValueError('Gemini manual import is not enabled.')
            for key in ['Prompt_ID', 'model_key', 'run_number', 'prompt_text']:
                if item[key] != row[key]:
                    raise ValueError(f'{identity}: mismatched {key}')
            if row['generation_status'] not in ('NOT_RUN', 'FAILED'):
                raise ValueError(f'{identity}: refusing to replace received/uncertain API response')
            stamp = datetime.fromisoformat(item['collected_at'])
            if stamp.tzinfo is None:
                raise ValueError('collected_at needs a timezone, e.g. +05:00')
            if not item['model_version_displayed'].strip() or not item['collection_interface'].strip():
                raise ValueError('Record displayed model and collection interface.')
            row.update(raw_response=item['raw_response'], run_date_time=item['collected_at'],
                api_status_before_manual=row['generation_status'], generation_status='MANUAL_RECEIVED',
                model_version_exact='', provider_status='MANUAL', session_or_request_id='', response_id='',
                collection_method=item['collection_interface'], conversation_url=item['conversation_url'],
                settings_notes=item['settings_notes'])
            # Displayed labels are not asserted to be immutable API versions.
            row['settings_notes'] = 'Displayed model: ' + item['model_version_displayed'] + '; ' + row['settings_notes']
    temp = base.with_suffix('.tmp')
    with temp.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows.values():
            row.setdefault('collection_method', 'API' if row['generation_status'] != 'NOT_RUN' else '')
            w.writerow(row)
    temp.replace(base)
    print(f'Merged {len(seen)} manual responses: {base}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['template', 'merge'])
    parser.add_argument('--profile', choices=['selected200', 'frozen500'], default='selected200')
    parser.add_argument('--file', type=Path)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    try:
        if args.profile == 'selected200':
            from selected_plan import load_selected_plan
            plan = load_selected_plan()
        else:
            plan = load_plan()
        args.file = args.file or ROOT / ('data/manual_selected200.csv' if args.profile == 'selected200' else 'data/manual_responses.csv')
        args.output_dir = args.output_dir or ROOT / ('results/selected200' if args.profile == 'selected200' else 'results/generation')
        args.output_dir.mkdir(parents=True, exist_ok=True)
        if args.action == 'template':
            template(args.file, plan)
            print(f'Created manual-response slots for {args.profile}: {args.file}')
        else:
            merge(args.file, args.output_dir, plan)
    except (ValueError, KeyError, OSError) as error:
        parser.exit(1, f'ERROR: {error}\n')
