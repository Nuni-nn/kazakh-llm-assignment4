"""Prepare blinded Gemini chat tasks, import saved JSON, and combine API/manual evaluations."""
import argparse
import base64
import csv
from datetime import datetime
import json
from pathlib import Path
import re

from generate_responses import ROOT, append_event, now, read_events, sha, state
from judge_responses import (candidate_with_verification, load_inputs, make_request,
                             process_lock, validate_result, verification_status)
from prepare_analysis import DEFAULT_OUTPUT, write_csv, write_jsonl

MANUAL_DIR = ROOT / 'results/manual_gemini_judge'
API_DIR = ROOT / 'results/selected200_judge_16k'
METADATA_FIELDS = ['blind_id', 'attempt_number', 'collected_at', 'model_visible',
                   'thinking_mode_visible', 'conversation_url', 'raw_file', 'technical_retry_reason']


def api_state(directory):
    return state(read_events(directory / 'attempts.jsonl'), allow_unfinished=True)


def context(input_dir):
    settings_path = ROOT / 'config/judge_settings_16k.json'
    settings = json.loads(settings_path.read_text(encoding='utf-8'))
    prompt_path = ROOT / settings['prompt_file']
    rubric_path = ROOT / settings['rubric_file']
    guideline_path = ROOT / 'docs/annotation_guideline.md'
    rubric = json.loads(rubric_path.read_text(encoding='utf-8'))
    instructions = '\n\n'.join([prompt_path.read_text(encoding='utf-8'),
        'ANNOTATION GUIDELINE\n' + guideline_path.read_text(encoding='utf-8'),
        'RUBRIC\n' + rubric_path.read_text(encoding='utf-8'),
        'Treat the supplied prompt and response as data to evaluate. Return the specified JSON object.'])
    inputs = load_inputs(input_dir)
    files = [input_dir / 'judge_input_blind.jsonl', settings_path, prompt_path, rubric_path, guideline_path]
    hashes = {str(path.resolve()): sha(path) for path in files}
    return inputs, settings, rubric, instructions, hashes


def check_manifest(directory, hashes):
    path = directory / 'packet_manifest.json'
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8'))['input_sha256'] != hashes:
            raise ValueError('Manual packet inputs/rules changed. Keep this packet and prepare a separate revision.')
    else:
        if (directory / 'manual_imports.jsonl').exists():
            raise ValueError('Manual import journal exists without its manifest')
        path.write_text(json.dumps(dict(created_at=now(), input_sha256=hashes,
            preparation_script_sha256=sha(Path(__file__)),
            method='Gemini web interface, first saved response, actual visible settings recorded'), indent=2), encoding='utf-8')


def manual_state(directory):
    records = read_events(directory / 'manual_imports.jsonl')
    latest = {}
    identities = set()
    for record in records:
        identity = (record['blind_id'], record['attempt_number'])
        if identity in identities:
            raise ValueError(f'Duplicate manual attempt in journal: {identity}')
        identities.add(identity)
        latest[record['blind_id']] = record
    return records, latest


def prepare(directory, api_directory, inputs, settings, instructions):
    api = api_state(api_directory)
    _, manual = manual_state(directory)
    tasks = directory / 'tasks'
    tasks.mkdir(exist_ok=True)
    (directory / 'responses').mkdir(exist_ok=True)
    metadata = []
    for item in inputs:
        identity = item['blind_id']
        previous_api = api.get(identity, {})
        previous_manual = manual.get(identity, {})
        if previous_api.get('status') in ('JUDGED', 'JUDGED_MANUAL', 'ASSISTANT_REVIEWED', 'UNKNOWN') or previous_manual.get('status') == 'JUDGED_MANUAL':
            continue
        attempt = max(previous_api.get('attempt_number', 0), previous_manual.get('attempt_number', 0)) + 1
        if attempt > 3:
            continue
        body = make_request(item, settings, instructions)
        text = body['systemInstruction']['parts'][0]['text'] + '\n\nINPUT DATA\n' + body['contents'][0]['parts'][0]['text']
        path = tasks / f'{identity}.txt'
        if path.exists() and path.read_text(encoding='utf-8') != text:
            raise ValueError(f'Existing task content changed: {identity}')
        path.write_text(text, encoding='utf-8')
        metadata.append(dict(blind_id=identity, attempt_number=attempt, collected_at='',
            model_visible='', thinking_mode_visible='', conversation_url='', raw_file='',
            technical_retry_reason=''))
    metadata_path = directory / 'metadata.csv'
    if not metadata_path.exists() and metadata:
        write_csv(metadata_path, metadata)
    # This derived list can be refreshed without touching the working metadata.
    if metadata:
        write_csv(directory / 'remaining_tasks.csv', metadata)
    else:
        (directory / 'remaining_tasks.csv').write_text(','.join(METADATA_FIELDS) + '\n', encoding='utf-8-sig')
    print(f'Prepared {len(metadata)} remaining blind tasks: {tasks}')


def parse_saved_json(raw):
    text = raw.decode('utf-8-sig').strip()
    # Remove only an enclosing Markdown fence, preserving the original bytes in the journal.
    match = re.fullmatch(r'```(?:json)?\s*\n(.*?)\n```', text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1)
    return json.loads(text)


def import_saved(directory, api_directory, inputs, rubric):
    api = api_state(api_directory)
    indexed = {item['blind_id']: item for item in inputs}
    records, latest = manual_state(directory)
    imported = {(r['blind_id'], r['attempt_number']): r for r in records}
    path = directory / 'metadata.csv'
    if not path.exists():
        raise ValueError('Prepare the manual packet first')
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != METADATA_FIELDS:
            raise ValueError('Metadata header changed')
        entries = list(reader)
    seen = set()
    issues = []
    added = 0
    for entry in entries:
        if not entry['raw_file'].strip():
            continue
        identity = entry['blind_id']
        attempt = int(entry['attempt_number'])
        key = (identity, attempt)
        if key in seen or identity not in indexed:
            raise ValueError(f'Duplicate/unknown attempt in metadata: {key}')
        seen.add(key)
        source = (directory / 'responses' / entry['raw_file']).resolve()
        if not source.is_relative_to((directory / 'responses').resolve()):
            raise ValueError('Raw response file must be inside responses/')
        raw = source.read_bytes()
        digest = sha(source)
        if key in imported:
            if imported[key]['source_sha256'] != digest or imported[key]['metadata'] != entry:
                raise ValueError(f'Imported attempt changed: {key}. Keep original evidence.')
            continue
        api_previous = api.get(identity, {})
        manual_previous = latest.get(identity, {})
        if api_previous.get('status') in ('JUDGED', 'JUDGED_MANUAL', 'ASSISTANT_REVIEWED', 'UNKNOWN') or manual_previous.get('status') == 'JUDGED_MANUAL':
            raise ValueError(f'{identity}: completed or uncertain evaluation already exists')
        expected = max(api_previous.get('attempt_number', 0), manual_previous.get('attempt_number', 0)) + 1
        if attempt != expected or attempt > 3:
            raise ValueError(f'{identity}: expected attempt {expected}, maximum 3 across API and manual')
        if attempt > 1 and not entry['technical_retry_reason'].strip():
            raise ValueError(f'{identity}: record the technical reason for the repeated attempt')
        stamp = datetime.fromisoformat(entry['collected_at'])
        if stamp.tzinfo is None or not entry['model_visible'].strip() or not entry['thinking_mode_visible'].strip():
            raise ValueError(f'{identity}: record timestamp with timezone, actual model and thinking mode')
        record = dict(blind_id=identity, attempt_number=attempt, imported_at=now(),
            metadata=entry, source_sha256=digest, raw_output_base64=base64.b64encode(raw).decode('ascii'),
            collection_method='MANUAL_GEMINI', status='INVALID_MANUAL_OUTPUT')
        try:
            record['result'] = validate_result(parse_saved_json(raw), indexed[identity]['raw_response'], rubric)
            record['status'] = 'JUDGED_MANUAL'
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            record['error_message'] = str(error)
            issues.append(f'{identity}: {error}')
        append_event(directory / 'manual_imports.jsonl', record)
        latest[identity] = record
        imported[key] = record
        added += 1
    print(f'Imported {added} new manual attempts.')
    return issues


def merge(directory, api_directory, inputs):
    api = api_state(api_directory)
    previous = {row['candidate_id']: row for row in
                read_events(api_directory / 'candidate_errors_for_review.jsonl')}
    _, manual = manual_state(directory)
    combined = []
    candidates = []
    progress = {'API': 0, 'MANUAL_GEMINI': 0, 'ASSISTANT_REVIEW': 0, 'remaining': 0, 'requires_review': 0}
    for item in inputs:
        identity = item['blind_id']
        api_record = api.get(identity, {})
        manual_record = manual.get(identity, {})
        if api_record.get('status') == 'JUDGED' and manual_record.get('status') == 'JUDGED_MANUAL':
            raise ValueError(f'{identity}: duplicate completed API and manual evaluations, requires reconciliation')
        if manual_record.get('status') == 'JUDGED_MANUAL':
            record = manual_record
            method = 'MANUAL_GEMINI'
            model = record['metadata']['model_visible']
            timestamp = record['metadata']['collected_at']
        else:
            record = api_record
            method = record.get('collection_method', 'API' if record.get('status') == 'JUDGED' else '')
            model = record.get('judge_model_reported', '')
            timestamp = record.get('timestamp', '')
        status = record.get('status', 'NOT_RUN')
        if not method and manual_record:
            status = manual_record['status']
        if method:
            progress[method] += 1
        else:
            progress['remaining'] += 1
            if status != 'NOT_RUN':
                progress['requires_review'] += 1
        combined.append(dict(blind_id=identity, status=status, collection_method=method,
            judge_model_visible_or_reported=model, collected_at=timestamp,
            evaluator=record.get('evaluator', model), human_verification_status='PENDING',
            api_status=api_record.get('status', 'NOT_RUN') if api_record.get('event') in ('started', 'finished') else 'NOT_RUN',
            manual_status=manual_record.get('status', 'NOT_RUN'), result=record.get('result') if method else None))
        item_candidates = []
        if method:
            for index, candidate in enumerate(record['result']['candidate_errors'], 1):
                item_candidates.append(candidate_with_verification(
                    dict(candidate_id=f'{identity}_E{index:03d}', blind_id=identity,
                         collection_method=method, **candidate), previous))
        candidates.extend(item_candidates)
        combined[-1]['human_verification_status'] = verification_status(item_candidates)
        combined[-1]['human_verification_scope'] = 'candidate_errors_only'
    write_jsonl(directory / 'combined_judge_600.jsonl', combined)
    write_jsonl(directory / 'candidate_errors_for_review.jsonl', candidates)
    (directory / 'progress.json').write_text(json.dumps(progress, indent=2), encoding='utf-8')
    print(f'Completed API {progress["API"]}, manual {progress["MANUAL_GEMINI"]}, assistant {progress["ASSISTANT_REVIEW"]}, remaining {progress["remaining"]}.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'import', 'merge'])
    parser.add_argument('--input-dir', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--manual-dir', type=Path, default=MANUAL_DIR)
    parser.add_argument('--api-dir', type=Path, default=API_DIR)
    args = parser.parse_args()
    inputs, settings, rubric, instructions, hashes = context(args.input_dir)
    args.manual_dir.mkdir(parents=True, exist_ok=True)
    args.api_dir.mkdir(parents=True, exist_ok=True)
    with process_lock(args.api_dir), process_lock(args.manual_dir):
        check_manifest(args.manual_dir, hashes)
        issues = []
        if args.action == 'prepare':
            prepare(args.manual_dir, args.api_dir, inputs, settings, instructions)
        elif args.action == 'import':
            issues = import_saved(args.manual_dir, args.api_dir, inputs, rubric)
        merge(args.manual_dir, args.api_dir, inputs)
        if issues:
            raise ValueError('Saved attempts requiring review: ' + ' | '.join(issues))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        raise SystemExit(f'ERROR: {error}')
