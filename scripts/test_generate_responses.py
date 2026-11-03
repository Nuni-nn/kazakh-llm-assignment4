"""Offline tests: never contact providers."""
import base64
import csv
import json
import shutil
import uuid
import unittest
from pathlib import Path
from unittest.mock import patch

import generate_responses as g


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.out = g.ROOT / ('.generation-test-' + uuid.uuid4().hex)
        self.out.mkdir()
        assert self.out.resolve().parent == g.ROOT.resolve()
        self.addCleanup(shutil.rmtree, self.out)
        self.plan = g.load_plan()[:1]

    def run_fake(self, responses):
        with patch.dict(g.os.environ, {'OPENAI_API_KEY': 'offline-test'}), \
             patch.object(g, 'send', side_effect=responses) as sender, \
             patch.object(g.time, 'sleep'):
            g.execute(self.plan, self.out, 1, 0)
        return sender

    def test_plan(self):
        plan = g.load_plan()
        self.assertEqual(len(plan), 4500)
        self.assertEqual([x['run_number'] for x in plan[:3]], [1, 2, 3])
        self.assertEqual(len({x['run_id'] for x in plan}), 4500)

    def test_selected_plan_is_separate_and_has_larger_gemini_limit(self):
        from selected_plan import load_selected_plan
        plan = load_selected_plan()
        self.assertEqual(len(plan), 600)
        self.assertEqual(len({r['prompt']['Prompt_ID'] for r in plan}), 200)
        self.assertEqual({r['run_number'] for r in plan}, {1})
        self.assertTrue(all(r['run_id'].startswith('S200_') for r in plan))
        self.assertTrue(all(r['model']['max_output_tokens'] == 8192 for r in plan
                            if r['model']['model_key'] == 'gemini36_flash'))

    def test_manual_merge_preserves_original_text_and_logs(self):
        import manual_responses as manual
        source = self.out / 'manual.csv'
        manual.template(source)
        with source.open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames
            rows = list(reader)
        self.assertEqual(len(rows), 3000)
        rows[0].update(raw_response='  unchanged\ntext  ', response_saved='yes',
                       model_version_displayed='Displayed GPT', collected_at='2026-11-02T15:00:00+05:00',
                       collection_interface='chat UI')
        with source.open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader(); writer.writerows(rows)
        manual.merge(source, self.out)
        with (self.out / 'responses_with_manual.csv').open(encoding='utf-8-sig', newline='') as f:
            combined = list(csv.DictReader(f))
        self.assertEqual(len(combined), 4500)
        self.assertEqual(combined[0]['raw_response'], '  unchanged\ntext  ')
        self.assertEqual(combined[0]['generation_status'], 'MANUAL_RECEIVED')
        self.assertEqual(combined[0]['model_version_exact'], '')
        self.assertFalse((self.out / 'attempts.jsonl').exists())

    def test_unselected_provider_is_not_called(self):
        plan = g.load_plan()[:9]
        with patch.dict(g.os.environ, {'OPENAI_API_KEY': 'offline-test'}), \
             patch.object(g, 'send', return_value=(200, {}, b'{"output": []}', '')) as sender:
            g.execute(plan, self.out, 1, 0, {'gpt6_astra'})
        self.assertEqual(sender.call_count, 3)
        with (self.out / 'responses_raw.csv').open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 9)
        self.assertTrue(all(r['generation_status'] == 'NOT_RUN' for r in rows if r['model_key'] != 'gpt6_astra'))

    def test_raw_text_and_resume(self):
        text = '  Қазақша\nжауап!  '
        raw = json.dumps({'model': 'exact-version', 'id': 'response1', 'status': 'completed',
                          'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': text}]}]}).encode()
        self.run_fake([(200, {'x-request-id': 'req1'}, raw, '')])
        sender = self.run_fake([])
        sender.assert_not_called()
        event = g.state(g.read_events(self.out / 'attempts.jsonl'))['RUN0001']
        self.assertEqual(event['raw_response'], text)
        self.assertEqual(base64.b64decode(event['raw_http_body_base64']), raw)
        self.assertEqual(event['model_version_exact'], 'exact-version')

    def test_maximum_three_attempts_and_failed_run_retained(self):
        sender = self.run_fake([(429, {}, b'limited', 'rate limit')] * 3)
        self.assertEqual(sender.call_count, 3)
        sender = self.run_fake([])
        sender.assert_not_called()
        with (self.out / 'responses_raw.csv').open(encoding='utf-8-sig', newline='') as f:
            row = next(csv.DictReader(f))
        self.assertEqual(row['generation_status'], 'FAILED')
        self.assertEqual(row['retry_count'], '2')

    def test_retry_resume_keeps_attempt_budget(self):
        start = {'event': 'started', 'run_id': 'RUN0001', 'attempt_number': 1}
        finish = dict(start, event='finished', status='RETRY_PENDING')
        g.append_event(self.out / 'attempts.jsonl', start)
        g.append_event(self.out / 'attempts.jsonl', finish)
        sender = self.run_fake([(503, {}, b'', 'server')] * 2)
        self.assertEqual(sender.call_count, 2)

    def test_empty_response_not_retried(self):
        sender = self.run_fake([(200, {}, b'{"output": []}', '')])
        self.assertEqual(sender.call_count, 1)
        self.assertEqual(g.state(g.read_events(self.out / 'attempts.jsonl'))['RUN0001']['status'], 'RECEIVED')

    def test_exhausted_quota_pauses_without_consuming_retries(self):
        with self.assertRaisesRegex(ValueError, 'quota exhausted'):
            self.run_fake([(429, {}, b'{"error":{"code":"credit_balance_exhausted"}}', 'quota')])
        event = g.state(g.read_events(self.out / 'attempts.jsonl'))['RUN0001']
        self.assertEqual(event['attempt_number'], 1)
        self.assertEqual(event['status'], 'RETRY_PENDING')
        self.assertTrue(g.exhausted_quota(429, b'Generate content requests per day limit exceeded on Free Tier'))
        self.assertFalse(g.exhausted_quota(429, b'temporary rate limit'))

    def test_uncertain_request_cannot_be_resent(self):
        g.append_event(self.out / 'attempts.jsonl', {'event': 'started', 'run_id': 'RUN0001', 'attempt_number': 1})
        with self.assertRaisesRegex(ValueError, 'Unfinished request'):
            g.state(g.read_events(self.out / 'attempts.jsonl'))
        self.run_fake([]).assert_not_called()
        self.assertEqual(g.state(g.read_events(self.out / 'attempts.jsonl'), True)['RUN0001']['status'], 'UNKNOWN')

    def test_bad_credentials_stop_without_retry(self):
        with self.assertRaisesRegex(ValueError, 'HTTP 401'):
            self.run_fake([(401, {}, b'unauthorized', 'unauthorized')])
        self.run_fake([]).assert_not_called()

    def test_provider_payloads_and_visible_text(self):
        for model in g.load_settings(g.CONFIG)['test_models']:
            _, _, body = g.request_spec(model, 'unchanged prompt', 'offline')
            self.assertNotIn('temperature', body)
            self.assertNotIn('top_p', body)
        text, version, _, _ = g.extract('gemini36_flash', {'modelVersion': 'v1', 'candidates': [
            {'content': {'parts': [{'thought': True, 'text': 'private'}, {'text': ' visible '}]}}]})
        self.assertEqual((text, version), (' visible ', 'v1'))
        self.assertEqual(g.extract('claude_sonnet55', {'content': [
            {'type': 'thinking', 'thinking': 'private'}, {'type': 'text', 'text': ' answer '} ]})[0], ' answer ')


if __name__ == '__main__':
    unittest.main()
