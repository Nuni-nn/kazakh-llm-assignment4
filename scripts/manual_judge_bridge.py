"""Local UI for copying blind tasks and saving first Gemini web responses."""
import csv
import base64
import html
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import manual_judge as manual
from generate_responses import now

DIRECTORY = manual.MANUAL_DIR
INPUTS, SETTINGS, RUBRIC, INSTRUCTIONS, HASHES = manual.context(manual.DEFAULT_OUTPUT)
INDEXED = {item['blind_id']: item for item in INPUTS}


def pending():
    api = manual.api_state(manual.API_DIR)
    _, saved = manual.manual_state(DIRECTORY)
    for item in INPUTS:
        identity = item['blind_id']
        api_record = api.get(identity, {})
        record = saved.get(identity, {})
        if api_record.get('status') in ('JUDGED', 'UNKNOWN') or record.get('status') == 'JUDGED_MANUAL':
            continue
        attempt = max(api_record.get('attempt_number', 0), record.get('attempt_number', 0)) + 1
        if attempt <= 3:
            yield identity, attempt


def save(fields):
    identity = fields['blind_id']
    attempt = int(fields['attempt_number'])
    if (identity, attempt) not in set(pending()):
        raise ValueError('Task already completed or attempt number changed')
    if not fields['response'].strip():
        raise ValueError('Response is empty')
    filename = f'{identity}_attempt{attempt}.txt'
    path = DIRECTORY / 'responses' / filename
    if path.exists():
        raise ValueError('Raw response already saved, reconcile existing evidence first')
    metadata_path = DIRECTORY / 'metadata.csv'
    with metadata_path.open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    entry = dict(blind_id=identity, attempt_number=str(attempt), collected_at=fields['collected_at'],
        model_visible=fields['model_visible'], thinking_mode_visible=fields['thinking_mode_visible'],
        conversation_url=fields['conversation_url'], raw_file=filename,
        technical_retry_reason=fields.get('technical_retry_reason', ''))
    row = next((r for r in rows if r['blind_id'] == identity and r['attempt_number'] == str(attempt)
                and not r['raw_file']), None)
    if row is None:
        rows.append(entry)
    else:
        row.update(entry)
    path.write_text(fields['response'], encoding='utf-8')
    if fields.get('screenshot_base64'):
        (DIRECTORY / 'responses' / f'{identity}_attempt{attempt}.png').write_bytes(
            base64.b64decode(fields['screenshot_base64']))
    manual.write_csv(metadata_path, rows)
    issues = manual.import_saved(DIRECTORY, manual.API_DIR, INPUTS, RUBRIC)
    manual.merge(DIRECTORY, manual.API_DIR, INPUTS)
    if issues:
        return 'SAVED_REQUIRES_REVIEW ' + ' | '.join(issues)
    return f'SAVED {identity}'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def render(self, message=''):
        available = list(pending())
        requested = parse_qs(urlparse(self.path).query).get('id', [''])[0]
        task = next((entry for entry in available if entry[0] == requested), available[0] if available else None)
        progress = json.loads((DIRECTORY / 'progress.json').read_text(encoding='utf-8'))
        if task is None:
            form = '<p>No remaining eligible tasks.</p>'
        else:
            identity, attempt = task
            text = (DIRECTORY / 'tasks' / f'{identity}.txt').read_text(encoding='utf-8')
            form = f'''<p id="task-id">{identity}</p><p id="attempt">{attempt}</p>
            <label>Task text<textarea id="task" readonly>{html.escape(text)}</textarea></label>
            <form method="POST" action="/save">
            <input type="hidden" name="blind_id" value="{identity}">
            <input type="hidden" name="attempt_number" value="{attempt}">
            <label>Raw Gemini response<textarea name="response" required></textarea></label>
            <label>Collected at<input name="collected_at" value="{now()}" required></label>
            <label>Visible model<input name="model_visible" required></label>
            <label>Visible thinking mode<input name="thinking_mode_visible" required></label>
            <label>Conversation URL<input name="conversation_url" required></label>
            <label>Technical retry reason<input name="technical_retry_reason"></label>
            <label>Screenshot base64<textarea name="screenshot_base64"></textarea></label>
            <button>Save evaluation</button></form>'''
        page = f'''<!doctype html><html><meta charset="utf-8"><title>Local Judge Collection</title>
        <style>body{{font:16px sans-serif;margin:24px;max-width:1000px}}label{{display:block;margin:12px 0}}
        textarea{{display:block;width:100%;height:200px}}input{{display:block;width:100%}}</style>
        <h1>Local Judge Collection</h1><p id="message">{html.escape(message)}</p>
        <p id="progress">{html.escape(json.dumps(progress))}</p>{form}</html>'''
        content = page.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        self.render()

    def do_POST(self):
        if self.headers.get('Origin') not in (None, f'http://127.0.0.1:{self.server.server_port}'):
            self.send_error(403)
            return
        data = self.rfile.read(int(self.headers.get('Content-Length', '0'))).decode('utf-8')
        fields = {key: values[0] for key, values in parse_qs(data, keep_blank_values=True).items()}
        try:
            with manual.process_lock(manual.API_DIR), manual.process_lock(DIRECTORY):
                manual.check_manifest(DIRECTORY, HASHES)
                message = save(fields)
        except (ValueError, KeyError, OSError) as error:
            message = 'ERROR ' + str(error)
        self.render(message)


if __name__ == '__main__':
    server = HTTPServer(('127.0.0.1', 5992), Handler)
    print(f'http://127.0.0.1:{server.server_port}', flush=True)
    server.serve_forever()
