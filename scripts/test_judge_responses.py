"""Regression checks for blinded payloads, schema validation and resume safety."""
import json
import shutil
import unittest
import uuid
from unittest.mock import patch

import judge_responses as judge


class JudgeTests(unittest.TestCase):
    def setUp(self):
        self.output = judge.ROOT / ('.generation-test-' + uuid.uuid4().hex)
        self.output.mkdir()
        self.addCleanup(shutil.rmtree, self.output)
        self.item = dict(blind_id='B0001', Prompt_KK='Prompt', raw_response=' Exact response. ',
                         Task_Category='Description', Subset='Open-ended')
        self.settings = dict(model='gemini-3.6-flash', max_output_tokens=4096, thinking_level='high')
        self.rubric = json.loads((judge.ROOT / 'config/judge_rubric.json').read_text(encoding='utf-8'))
        self.result = dict(scores={name: 4 for name in judge.SCORES}, candidate_errors=[],
                           instruction_compliance={'passed': True, 'notes': ''}, short_summary='OK')

    def call(self, responses):
        with patch.dict(judge.os.environ, {'GEMINI_API_KEY': 'offline-test'}), \
             patch.object(judge, 'send', side_effect=responses) as sender, \
             patch.object(judge.time, 'sleep'):
            judge.run([self.item], self.output, self.settings, 'Full instructions', self.rubric, 0, 1)
        return sender

    def test_payload_has_no_mapping_or_model_group(self):
        body = judge.make_request(self.item, self.settings, 'Instructions')
        content = json.loads(body['contents'][0]['parts'][0]['text'])
        self.assertEqual(set(content), {'Prompt_KK', 'raw_response', 'Task_Category', 'Subset'})
        self.assertEqual(content['raw_response'], self.item['raw_response'])
        self.assertNotIn('tools', body)

    def test_success_is_not_repeated(self):
        payload = dict(modelVersion='reported-version', candidates=[dict(finishReason='STOP',
            content={'parts': [{'text': json.dumps(self.result)}]})])
        self.call([(200, {}, json.dumps(payload).encode(), '')])
        self.call([]).assert_not_called()
        result = json.loads((self.output / 'judge_results.jsonl').read_text(encoding='utf-8'))
        self.assertEqual(result['status'], 'JUDGED')
        self.assertEqual(result['result'], self.result)

    def test_quota_pauses_after_first_attempt(self):
        with self.assertRaisesRegex(ValueError, 'quota/rate limit'):
            self.call([(429, {}, b'{"error":{"code":429}}', 'quota')])
        events = judge.read_events(self.output / 'attempts.jsonl')
        self.assertEqual(len(events), 2)
        self.assertEqual(events[-1]['status'], 'RETRY_PENDING')

    def test_truncation_is_saved_and_not_retried(self):
        payload = {'candidates': [{'finishReason': 'MAX_TOKENS', 'content': {'parts': [{'text': '{'}]}}]}
        with self.assertRaisesRegex(ValueError, 'JSON/truncation'):
            self.call([(200, {}, json.dumps(payload).encode(), '')])
        self.call([]).assert_not_called()
        event = judge.read_events(self.output / 'attempts.jsonl')[-1]
        self.assertEqual(event['judge_text'], '{')
        self.assertEqual(event['status'], 'INVALID_JUDGE_OUTPUT')

    def test_bad_span_is_rejected(self):
        self.result['candidate_errors'] = [dict(span='invented', primary_category='Lexical',
            supplementary_labels=[], confidence=0.9, suggested_correction='x', justification='y')]
        with self.assertRaisesRegex(ValueError, 'substring'):
            judge.validate_result(self.result, self.item['raw_response'], self.rubric)

    def test_inapplicable_correction_may_be_null(self):
        self.result['candidate_errors'] = [dict(span='response', primary_category=None,
            supplementary_labels=['Instruction / format'], confidence=0.95,
            suggested_correction=None, justification='Supplementary issue only')]
        self.assertIs(judge.validate_result(self.result, self.item['raw_response'], self.rubric), self.result)

    def test_unknown_request_is_not_repeated(self):
        judge.append_event(self.output / 'attempts.jsonl', dict(event='started', run_id='B0001', attempt_number=1))
        self.call([]).assert_not_called()
        result = json.loads((self.output / 'judge_results.jsonl').read_text(encoding='utf-8'))
        self.assertEqual(result['status'], 'UNKNOWN')

    def test_human_confirmation_survives_export(self):
        candidate = dict(span='response', primary_category='Lexical',
            supplementary_labels=[], confidence=0.9, suggested_correction='answer', justification='Example')
        self.result['candidate_errors'] = [candidate]
        events = [dict(event='finished', run_id='B0001', attempt_number=1,
                       status='JUDGED', result=self.result)]
        judge.export_results([self.item], events, self.output)
        path = self.output / 'candidate_errors_for_review.jsonl'
        saved = judge.read_events(path)
        saved[0]['human_verification'] = dict(decision='CONFIRMED', basis='USER_REPORT')
        judge.write_jsonl(path, saved)
        judge.export_results([self.item], events, self.output)
        result = judge.read_events(self.output / 'judge_results.jsonl')[0]
        self.assertEqual(result['human_verification_status'], 'CONFIRMED_USER_REPORTED')
        self.assertEqual(judge.read_events(path)[0]['human_verification']['basis'], 'USER_REPORT')
        candidate['primary_category'] = 'Grammatical'
        judge.export_results([self.item], events, self.output)
        self.assertEqual(judge.read_events(self.output / 'judge_results.jsonl')[0]
                         ['human_verification_status'], 'PENDING')
        self.assertNotIn('human_verification', judge.read_events(path)[0])


if __name__ == '__main__':
    unittest.main()
