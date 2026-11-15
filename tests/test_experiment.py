import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiment.core import call_model, load_questions, parse_judgment, prompt_for, score

ROOT = Path(__file__).resolve().parents[1]

class ExperimentTests(unittest.TestCase):
    def test_dataset_and_prompts(self):
        rows = load_questions(ROOT / 'data/questions.csv')
        self.assertEqual(len(rows), 30)
        row = rows[0]
        self.assertEqual(prompt_for(row, 'neutral'), row['question'])
        self.assertEqual(prompt_for(row, 'incorrect_suggestion'), row['incorrect_suggestion'])
        self.assertEqual(prompt_for(row, 'positive_opinion'), row['positive_opinion'])
        self.assertEqual(prompt_for(row, 'negative_opinion'), row['negative_opinion'] + '\n\n' + row['question'])

    def test_labels_and_missing_score(self):
        judgment = {'claims': [{'claim': 'a', 'label': 'supported', 'rationale': 'yes'}, {'claim': 'b', 'label': 'unverifiable', 'rationale': 'unknown'}], 'answer_completeness': 'partial', 'agreement': 'unclear', 'tone': 'neutral', 'notes': ''}
        parsed = parse_judgment(json.dumps(judgment))
        self.assertEqual(score(parsed)['factuality'], 50)
        parsed['claims'] = []
        self.assertIsNone(score(parsed)['factuality'])
        judgment['claims'][0]['label'] = 'true'
        with self.assertRaises(ValueError):
            parse_judgment(json.dumps(judgment))

    def test_provider_requests_and_incomplete_outputs(self):
        class Reply:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return json.dumps(self.data).encode()
        reply = Reply()
        reply.data = {'model': 'returned', 'choices': [{'finish_reason': 'stop', 'message': {'content': 'answer'}}], 'usage': {'total_tokens': 4}}
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'secret'}), patch('urllib.request.urlopen', return_value=reply) as urlopen:
            out = call_model({'id': 'x', 'provider': 'openai', 'model': 'test', 'max_tokens': 10}, 'hello')
            payload = json.loads(urlopen.call_args.args[0].data)
            self.assertEqual(payload['max_completion_tokens'], 10)
            self.assertEqual(out['returned_model'], 'returned')
            reply.data['choices'][0]['finish_reason'] = 'length'
            with self.assertRaises(ValueError):
                call_model({'id': 'x', 'provider': 'openai', 'model': 'test'}, 'hello')
        reply.data = {'model': 'claude-returned', 'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': 'answer'}], 'usage': {}}
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'secret'}), patch('urllib.request.urlopen', return_value=reply) as urlopen:
            result = call_model({'id': 'y', 'provider': 'anthropic', 'model': 'test', 'max_tokens': 20}, 'hello')
            self.assertEqual(json.loads(urlopen.call_args.args[0].data)['max_tokens'], 20)
            self.assertEqual(result['text'], 'answer')

    def test_failed_collection_does_not_receive_a_score(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / 'run'
            def cli(*args):
                subprocess.run([sys.executable, '-m', 'experiment', *map(str, args)], cwd=ROOT, capture_output=True, text=True, check=True)
            cli('run', '--config', 'examples/mock.json', '--limit', '1', '--out', dest)
            path = dest / 'responses.jsonl'
            records = [json.loads(line) for line in path.read_text().splitlines()]
            records[0].update(status='error', response=None, error='fixture failure')
            path.write_text(''.join(json.dumps(x) + '\n' for x in records))
            cli('grade', '--run', dest, '--judge', 'examples/mock-judge.json')
            cli('report', '--run', dest)
            with (dest / 'results.csv').open() as f:
                rows = list(csv.DictReader(f))
            failed = next(row for row in rows if row['record_id'] == records[0]['record_id'])
            self.assertEqual(failed['grade_status'], 'skipped')
            self.assertEqual(failed['factuality'], '')
            self.assertEqual(failed['error'], 'fixture failure')

    def test_end_to_end_and_paired_exclusions(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / 'run'
            def cli(*args):
                return subprocess.run([sys.executable, '-m', 'experiment', *map(str, args)], cwd=ROOT, capture_output=True, text=True, check=True)
            cli('run', '--config', 'examples/mock.json', '--limit', '1', '--out', dest)
            cli('grade', '--run', dest, '--judge', 'examples/mock-judge.json')
            grade_file = dest / 'grades.jsonl'
            grades = [json.loads(x) for x in grade_file.read_text().splitlines()]
            # Give all but one record real-looking test labels, independent of mock output.
            for grade in grades[:-1]:
                grade['judgment']['claims'] = [{'claim': 'test', 'label': 'supported', 'rationale': 'fixture'}]
            grade_file.write_text(''.join(json.dumps(x) + '\n' for x in grades))
            cli('report', '--run', dest)
            with (dest / 'results.csv').open() as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 8)
            self.assertEqual(sum(r['factuality'] == '' for r in rows), 1)
            with (dest / 'paired.csv').open() as f:
                pairs = list(csv.DictReader(f))
            self.assertGreater(len(pairs), 0)
            self.assertTrue(all(float(p['delta']) == 0 for p in pairs))
            (dest / 'review.csv').write_text('human edits\n')
            cli('report', '--run', dest)
            self.assertEqual((dest / 'review.csv').read_text(), 'human edits\n')
            repeated = subprocess.run([sys.executable, '-m', 'experiment', 'grade', '--run', str(dest), '--judge', 'examples/mock-judge.json'], cwd=ROOT, capture_output=True)
            self.assertNotEqual(repeated.returncode, 0)

if __name__ == '__main__':
    unittest.main()
