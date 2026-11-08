"""Offline regression checks for manual evidence and API/manual reconciliation."""
import csv
import json
import shutil
import unittest
import uuid

import manual_judge as manual


class ManualJudgeTests(unittest.TestCase):
    def setUp(self):
        self.root = manual.ROOT / ('.generation-test-' + uuid.uuid4().hex)
        self.root.mkdir()
        self.addCleanup(shutil.rmtree, self.root)
        self.directory = self.root / 'manual'
        self.api = self.root / 'api'
        self.directory.mkdir()
        self.api.mkdir()
        self.item = dict(blind_id='B0001', Prompt_KK='Prompt', raw_response='A response.',
                         Task_Category='Description', Subset='Open-ended')
        self.inputs = [self.item]
        self.settings = dict(max_output_tokens=16384, thinking_level='high')
        self.rubric = json.loads((manual.ROOT / 'config/judge_rubric.json').read_text(encoding='utf-8'))
        self.result = dict(scores={name: 4 for name in ['grammar', 'morphology', 'lexical_naturalness', 'overall_quality']},
            candidate_errors=[], instruction_compliance={'passed': True, 'notes': ''}, short_summary='OK')

    def prepare(self):
        manual.prepare(self.directory, self.api, self.inputs, self.settings, 'Full instructions')

    def fill_metadata(self, attempt=1, reason=''):
        raw = self.directory / 'responses/B0001.json'
        raw.write_text('```json\n' + json.dumps(self.result) + '\n```', encoding='utf-8')
        row = dict(blind_id='B0001', attempt_number=attempt, collected_at='2026-11-08T19:00:00+05:00',
            model_visible='Actual visible label', thinking_mode_visible='Unknown', conversation_url='',
            raw_file='B0001.json', technical_retry_reason=reason)
        manual.write_csv(self.directory / 'metadata.csv', [row])

    def test_round_trip_and_repeat_import(self):
        self.prepare()
        self.fill_metadata()
        self.assertEqual(manual.import_saved(self.directory, self.api, self.inputs, self.rubric), [])
        original = (self.directory / 'manual_imports.jsonl').read_bytes()
        manual.import_saved(self.directory, self.api, self.inputs, self.rubric)
        self.assertEqual((self.directory / 'manual_imports.jsonl').read_bytes(), original)
        manual.merge(self.directory, self.api, self.inputs)
        combined = json.loads((self.directory / 'combined_judge_600.jsonl').read_text(encoding='utf-8'))
        self.assertEqual(combined['collection_method'], 'MANUAL_GEMINI')
        self.assertEqual(combined['result'], self.result)

    def test_completed_api_not_in_manual_tasks(self):
        manual.append_event(self.api / 'attempts.jsonl', dict(event='finished', run_id='B0001',
            attempt_number=1, status='JUDGED', result=self.result))
        self.prepare()
        self.assertFalse((self.directory / 'tasks/B0001.txt').exists())

    def test_changed_import_is_rejected(self):
        self.prepare()
        self.fill_metadata()
        manual.import_saved(self.directory, self.api, self.inputs, self.rubric)
        (self.directory / 'responses/B0001.json').write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'attempt changed'):
            manual.import_saved(self.directory, self.api, self.inputs, self.rubric)

    def test_invalid_json_is_saved(self):
        self.prepare()
        self.fill_metadata()
        (self.directory / 'responses/B0001.json').write_text('{', encoding='utf-8')
        issues = manual.import_saved(self.directory, self.api, self.inputs, self.rubric)
        self.assertEqual(len(issues), 1)
        self.assertEqual(manual.manual_state(self.directory)[1]['B0001']['status'], 'INVALID_MANUAL_OUTPUT')

    def test_repeated_attempt_requires_technical_reason(self):
        manual.append_event(self.api / 'attempts.jsonl', dict(event='finished', run_id='B0001',
            attempt_number=1, status='INVALID_JUDGE_OUTPUT'))
        self.prepare()
        self.fill_metadata(attempt=2)
        with self.assertRaisesRegex(ValueError, 'technical reason'):
            manual.import_saved(self.directory, self.api, self.inputs, self.rubric)
        self.fill_metadata(attempt=2, reason='Invalid API JSON field types')
        manual.import_saved(self.directory, self.api, self.inputs, self.rubric)


if __name__ == '__main__':
    unittest.main()
