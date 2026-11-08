"""Frozen generation runner. Default: offline plan; --execute sends paid requests."""
import argparse
import base64
import csv
import hashlib
import json
import os
import platform
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from generation_config import load_settings

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/prompts_500_v1.0.csv'
CONFIG = ROOT / 'config/generation_settings.json'
EXPECTED_SHA = 'bb8303cf296bcfb0e418166d551a8a5e2790798bd5e3c7fdb7e7b5b22f4126ec'
FROZEN = [DATA, CONFIG, ROOT / 'config/judge_prompt.txt', ROOT / 'config/judge_rubric.json', ROOT / 'docs/retry_policy.md',
          ROOT / 'docs/annotation_guideline.md', ROOT / 'scripts/word_count.py']
ENV_KEYS = {'gpt6_astra': 'OPENAI_API_KEY', 'gemini36_flash': 'GEMINI_API_KEY',
            'claude_sonnet55': 'ANTHROPIC_API_KEY'}


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_plan():
    if sha(DATA) != EXPECTED_SHA:
        raise ValueError('Frozen dataset SHA-256 mismatch.')
    config = load_settings(CONFIG)
    with DATA.open(encoding='utf-8-sig', newline='') as f:
        prompts = list(csv.DictReader(f))
    assert len(prompts) == 500 and len({p['Prompt_ID'] for p in prompts}) == 500
    assert config['final_runs_per_prompt_model'] == 3
    assert [m['model_key'] for m in config['test_models']] == list(ENV_KEYS)
    # The supplied simplified config keeps retry rules in docs/retry_policy.md.
    plan = []
    for prompt in prompts:
        for model in config['test_models']:
            for repeat in range(1, 4):
                plan.append({'run_id': f'RUN{len(plan)+1:04d}', 'run_number': repeat,
                             'prompt': prompt, 'model': model})
    assert len(plan) == config['expected_total_responses'] == 4500
    return plan


def request_spec(model, text, key):
    name = model['model_key']
    headers = {'Content-Type': 'application/json'}
    if name == 'gpt6_astra':
        url = 'https://api.openai.com/v1/responses'
        headers['Authorization'] = f'Bearer {key}'
        body = {'model': model['model_id'], 'input': text, 'reasoning': model['reasoning'],
                'max_output_tokens': model['max_output_tokens'], 'tools': []}
    elif name == 'gemini36_flash':
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model['model_id']}:generateContent"
        headers['x-goog-api-key'] = key
        body = {'contents': [{'role': 'user', 'parts': [{'text': text}]}],
                'generationConfig': {'maxOutputTokens': model['max_output_tokens'],
                                     'thinkingConfig': {'thinkingLevel': model['thinking_level']}}}
    else:
        url = 'https://api.anthropic.com/v1/messages'
        headers.update({'x-api-key': key, 'anthropic-version': '2023-06-01'})
        body = {'model': model['model_id'], 'messages': [{'role': 'user', 'content': text}],
                'max_tokens': model['max_tokens'], 'thinking': model['thinking'],
                'output_config': model['output_config']}
    return url, headers, body


def send(url, headers, body, timeout):
    request = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode('utf-8'),
                                     headers=headers, method='POST')
    # urllib has no automatic application-level retries.
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, dict(response.headers), response.read(), ''
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read(), str(error)
    except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError, ssl.SSLError) as error:
        return 0, {}, b'', f'{type(error).__name__}: {error}'


def extract(model_key, payload):
    """Only visible output text, without strip/normalisation; full HTTP body is retained."""
    if model_key == 'gpt6_astra':
        text = ''.join(c.get('text', c.get('refusal', ''))
                       for item in payload.get('output', []) if item.get('type') == 'message'
                       for c in item.get('content', []) if c.get('type') in ('output_text', 'refusal'))
        return text, payload.get('model', ''), payload.get('status', ''), payload.get('id', '')
    if model_key == 'gemini36_flash':
        candidates = payload.get('candidates', [])
        first = candidates[0] if candidates else {}
        text = ''.join(p.get('text', '') for p in first.get('content', {}).get('parts', [])
                       if not p.get('thought', False))
        return text, payload.get('modelVersion', ''), first.get('finishReason', ''), payload.get('responseId', '')
    text = ''.join(c.get('text', '') for c in payload.get('content', []) if c.get('type') == 'text')
    return text, payload.get('model', ''), payload.get('stop_reason', ''), payload.get('id', '')


def append_event(path, event):
    with path.open('a', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(event, ensure_ascii=False) + '\n')
        f.flush()
        os.fsync(f.fileno())


def exhausted_quota(code, raw):
    """Distinguish exhausted credit/daily quota from a transient rate limit."""
    if code != 429:
        return False
    message = raw.decode('utf-8', errors='replace').lower()
    return any(marker in message for marker in (
        'insufficient_quota', 'credit_balance_exhausted',
        'requests per day limit exceeded', 'generate_requests_per_day',
        'generaterequestsperday', 'per day quota exceeded'))


def read_events(path):
    if not path.exists():
        return []
    # Fail closed on a damaged/truncated journal rather than silently resending a request.
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def state(events, allow_unfinished=False):
    started, finished = {}, {}
    for event in events:
        target = started if event['event'] == 'started' else finished
        identity = (event['run_id'], event['attempt_number'])
        if identity in target:
            raise ValueError(f'Duplicate journal event: {identity}')
        target[identity] = event
    if started.keys() != finished.keys() and not allow_unfinished:
        raise ValueError('Unfinished request in attempt journal. Do not resend automatically: '
                         'check provider logs and reconcile the journal before continuing.')
    latest = {}
    for event in finished.values():
        latest[event['run_id']] = event
    if allow_unfinished:
        for identity in started.keys() - finished.keys():
            latest[identity[0]] = dict(started[identity], status='UNKNOWN',
                error_message='Interrupted request: provider outcome unknown; no automatic resend.')
    return latest


FIELDS = ['run_id', 'Prompt_ID', 'Subset', 'Task_Category', 'Domain', 'Difficulty',
          'model_key', 'model_name', 'run_number', 'model_id_requested', 'model_version_exact',
          'run_date_time', 'prompt_text', 'raw_response', 'generation_status', 'provider_status',
          'session_or_request_id', 'response_id', 'attempt_count', 'retry_count', 'error_message']


def export_csv(plan, events, out):
    latest = state(events, allow_unfinished=True)
    temp = out.with_suffix('.tmp')
    with temp.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for run in plan:
            p, m = run['prompt'], run['model']
            e = latest.get(run['run_id'], {})
            row = {k: p[k] for k in ['Prompt_ID', 'Subset', 'Task_Category', 'Domain', 'Difficulty']}
            row.update(run_id=run['run_id'], run_number=run['run_number'], model_key=m['model_key'],
                       model_name=m['display_name'], model_id_requested=m['model_id'], prompt_text=p['Prompt_KK'],
                       generation_status=e.get('status', 'NOT_RUN'), attempt_count=e.get('attempt_number', 0),
                       retry_count=max(0, e.get('attempt_number', 0)-1), run_date_time=e.get('timestamp', ''))
            for key in ['raw_response', 'model_version_exact', 'provider_status', 'session_or_request_id',
                        'response_id', 'error_message']:
                row[key] = e.get(key, '')
            writer.writerow(row)
    temp.replace(out)


def execute(plan, directory, timeout, limit, selected_models=None):
    journal = directory / 'attempts.jsonl'
    events = read_events(journal)
    latest = state(events, allow_unfinished=True)
    export_csv(plan, events, directory / 'responses_raw.csv')
    completed = 0
    try:
        for run in plan:
            if selected_models is not None and run['model']['model_key'] not in selected_models:
                continue
            previous = latest.get(run['run_id'], {})
            if previous and previous['status'] != 'RETRY_PENDING':
                continue
            if limit and completed >= limit:
                break
            m = run['model']
            url, headers, body = request_spec(m, run['prompt']['Prompt_KK'], os.environ[ENV_KEYS[m['model_key']]])
            for attempt in range(previous.get('attempt_number', 0)+1, 4):
                common = {'run_id': run['run_id'], 'Prompt_ID': run['prompt']['Prompt_ID'],
                          'model_key': m['model_key'], 'run_number': run['run_number'],
                          'model_id_requested': m['model_id'], 'attempt_number': attempt}
                append_event(journal, dict(common, event='started', timestamp=now(), request_body=body))
                start = time.monotonic()
                code, response_headers, raw, error = send(url, headers, body, timeout)
                h = {k.lower(): v for k, v in response_headers.items()}
                retryable = code == 0 or code in (408, 429) or 500 <= code <= 599
                status = 'RETRY_PENDING' if retryable and attempt < 3 else 'FAILED'
                e = dict(common, event='finished', timestamp=now(), http_status=code,
                         elapsed_seconds=time.monotonic()-start, error_message=error,
                         session_or_request_id=h.get('x-request-id', h.get('request-id', h.get('x-goog-request-id', ''))),
                         raw_http_body_base64=base64.b64encode(raw).decode('ascii'),
                         response_headers=response_headers)
                if 200 <= code < 300:
                    # A valid HTTP response is terminal, even when empty, refused or truncated.
                    status = 'RECEIVED'
                    try:
                        payload = json.loads(raw)
                        text, version, finish, response_id = extract(m['model_key'], payload)
                        e.update(raw_response=text, model_version_exact=version,
                                 provider_status=finish, response_id=response_id)
                    except (ValueError, TypeError, AttributeError, KeyError) as error:
                        status = 'RECEIVED_UNPARSED'
                        e['error_message'] = f'Preserved HTTP response; parse error: {error}'
                e['status'] = status
                append_event(journal, e)
                events.append(e)
                export_csv(plan, events, directory / 'responses_raw.csv')
                print(f"{run['run_id']} {m['model_key']} repeat={run['run_number']} attempt={attempt}: {status}", flush=True)
                if exhausted_quota(code, raw):
                    raise ValueError('Provider credits/daily quota exhausted. Batch paused; '
                                     'journal and unused retry budget retained. Resolve quota before resuming.')
                if status != 'RETRY_PENDING':
                    break
                delay = min(60, 2 ** attempt)
                try:
                    delay = max(delay, min(60, float(h.get('retry-after', '0'))))
                except ValueError:
                    pass
                time.sleep(delay)
            completed += 1
            if code in (400, 401, 403, 404):
                raise ValueError(f'Provider configuration/access error HTTP {code}; stopped. '
                                 'This failed run is retained; no automatic model/settings substitution.')
    finally:
        export_csv(plan, events, directory / 'responses_raw.csv')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='Send real billable API requests.')
    parser.add_argument('--profile', choices=['selected200', 'frozen500'], default='selected200')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--limit', type=int, default=0, help='Stop after this many planned runs; 0 = all remaining.')
    parser.add_argument('--timeout', type=float, default=300)
    parser.add_argument('--models', nargs='+', choices=['openai', 'gemini', 'claude'],
                        default=['gemini'], help='Providers to execute in this batch (default: Gemini only).')
    args = parser.parse_args()
    if args.limit < 0 or args.timeout <= 0:
        parser.error('limit must be nonnegative and timeout positive')
    if args.profile == 'selected200':
        from selected_plan import load_selected_plan, SETTINGS
        plan = load_selected_plan()
        active_config = SETTINGS
        frozen_files = [DATA, SETTINGS, ROOT / 'data/selected_200_prompts.csv',
                        ROOT / 'docs/retry_policy.md', ROOT / 'scripts/word_count.py']
    else:
        plan = load_plan()
        active_config = CONFIG
        frozen_files = FROZEN
    if args.output_dir is None:
        args.output_dir = ROOT / ('results/selected200' if args.profile == 'selected200' else 'results/generation')
    print(f'Validated {args.profile}: {len(plan)} planned outputs. Default API provider: Gemini.')
    if not args.execute:
        print('Offline plan only. No requests sent. Use --execute to start/resume.')
        return
    if args.profile == 'selected200' and (ROOT / 'results/selected200_analysis/import_manifest.json').exists():
        raise ValueError('The completed 600-response tracker is imported. Continue with judge_responses.py.')
    provider_keys = dict(openai='gpt6_astra', gemini='gemini36_flash', claude='claude_sonnet55')
    selected = {provider_keys[p] for p in args.models}
    missing = [ENV_KEYS[k] for k in selected if not os.environ.get(ENV_KEYS[k])]
    if missing:
        raise ValueError('Missing environment variables: ' + ', '.join(missing))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    # OS lock releases automatically on process exit, including crashes.
    with (args.output_dir / '.lock').open('a+b') as lock:
        lock.seek(0)
        if os.name == 'nt':
            import msvcrt
            if lock.read(1) == b'':
                lock.write(b'0'); lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        hashes = {str(p.relative_to(ROOT)): sha(p) for p in frozen_files if p.is_file()}
        hashes['scripts/generate_responses.py'] = sha(Path(__file__))
        hashes['scripts/generation_config.py'] = sha(ROOT / 'scripts/generation_config.py')
        if args.profile == 'selected200':
            hashes['scripts/selected_plan.py'] = sha(ROOT / 'scripts/selected_plan.py')
        manifest_path = args.output_dir / 'manifest.json'
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            if manifest['file_sha256'] != hashes:
                changed = {p for p in hashes.keys() | manifest['file_sha256'].keys()
                           if hashes.get(p) != manifest['file_sha256'].get(p)}
                if not changed <= {'scripts/generate_responses.py', 'scripts/generation_config.py', 'scripts/selected_plan.py'}:
                    raise ValueError('Frozen experiment files differ from initial manifest. Resume refused.')
                # Preserve the initial evidence and record maintenance separately.
                history = args.output_dir / 'runner_revisions.jsonl'
                revision = {'timestamp': now(), 'previous_sha256': manifest['file_sha256'],
                            'current_sha256': hashes,
                            'reason': 'Runner maintenance; experiment configuration unchanged.'}
                if not history.exists() or json.loads(history.read_text(encoding='utf-8').splitlines()[-1])['current_sha256'] != hashes:
                    append_event(history, revision)
        else:
            if (args.output_dir / 'attempts.jsonl').exists():
                raise ValueError('Journal exists without its manifest.')
            manifest_path.write_text(json.dumps({'created_at': now(), 'planned_outputs': len(plan),
                'file_sha256': hashes, 'python': sys.version, 'platform': platform.platform(),
                'timeout_seconds': args.timeout, 'profile': args.profile,
                'settings': json.loads(active_config.read_text(encoding='utf-8'))},
                ensure_ascii=False, indent=2), encoding='utf-8')
        execute(plan, args.output_dir, args.timeout, args.limit, selected)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, AssertionError) as error:
        sys.exit(f'ERROR: {error}')
