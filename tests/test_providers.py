import contextlib
import io
import json
import os
import tempfile
import unittest
import urllib.error
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from experiment.__main__ import grade, plan, run
from experiment.core import call_model, validate_model

ROOT = Path(__file__).resolve().parents[1]
GEMINI = {'id': 'gemini-test', 'provider': 'gemini', 'model': 'gemini-4-argon',
          'max_tokens': 32768, 'timeout_seconds': 300}


def response(data):
    return io.BytesIO(json.dumps(data).encode())


def gemini_answer(parts=None, reason='STOP'):
    return {'candidates': [{'finishReason': reason, 'content': {'parts': parts or [{'text': 'Final answer.'}]}}],
            'modelVersion': 'gemini-returned-version', 'usageMetadata': {'totalTokenCount': 42}}


class ProviderTests(unittest.TestCase):
    def test_gemini_request_and_final_text(self):
        data = gemini_answer([{'thought': True, 'text': 'Private reasoning summary.'},
                              {'text': 'Final '}, {'text': 'answer.'}])
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}, clear=True), \
                patch('urllib.request.urlopen', return_value=response(data)) as send:
            result = call_model({**GEMINI, 'model': 'models/gemini-4-argon', 'temperature': 0.5}, 'Question?')
        request = send.call_args.args[0]
        self.assertEqual(request.full_url, 'https://generativelanguage.googleapis.com/v1beta/models/gemini-4-argon:generateContent')
        self.assertEqual(request.get_header('X-goog-api-key'), 'test-key')
        self.assertNotIn('test-key', request.full_url)
        body = json.loads(request.data)
        self.assertEqual(body['contents'], [{'role': 'user', 'parts': [{'text': 'Question?'}]}])
        self.assertEqual(body['generationConfig'], {'maxOutputTokens': 32768, 'temperature': 0.5})
        self.assertEqual(send.call_args.kwargs['timeout'], 300)
        self.assertEqual(result, {'text': 'Final answer.', 'returned_model': 'gemini-returned-version', 'usage': {'totalTokenCount': 42}})

    def test_gemini_rejects_nonfinal_outputs(self):
        blocked_rating = gemini_answer()
        blocked_rating['candidates'][0]['safetyRatings'] = [{'blocked': True}]
        cases = [
            {'promptFeedback': {'blockReason': 'SAFETY'}},
            {'candidates': []},
            gemini_answer(reason='MAX_TOKENS'),
            gemini_answer(reason='SAFETY'),
            gemini_answer([{'text': '   '}]),
            gemini_answer([{'thought': True, 'text': 'Only reasoning.'}]),
            gemini_answer([{'functionCall': {'name': 'unexpected'}}]),
            blocked_rating,
        ]
        for data in cases:
            with self.subTest(data=data), patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}, clear=True), \
                    patch('urllib.request.urlopen', return_value=response(data)):
                with self.assertRaises(ValueError):
                    call_model(GEMINI, 'Question?')

    def test_provider_http_error_is_recorded_without_body(self):
        error = urllib.error.HTTPError('https://generativelanguage.googleapis.com', 429, 'rate limited', {}, io.BytesIO(b'sensitive provider body'))
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}, clear=True), \
                patch('urllib.request.urlopen', side_effect=error) as send:
            with self.assertRaisesRegex(RuntimeError, '^gemini HTTP 429$'):
                call_model(GEMINI, 'Question?')
        self.assertEqual(send.call_count, 1)

    def test_selected_models_and_astra_request(self):
        args = Namespace(dataset=ROOT / 'data/questions.csv', config=ROOT / 'examples/models.json', limit=None)
        _, config, tasks = plan(args)
        self.assertEqual(len(tasks), 720)
        self.assertEqual([m['provider'] for m in config['models']].count('gemini'), 2)
        judge = json.loads((ROOT / 'examples/judge.json').read_text())
        self.assertEqual(judge['model'], 'gpt-6-astra')
        self.assertNotIn(judge['model'], [m['model'] for m in config['models']])
        reply = {'model': 'gpt-6-astra', 'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]}
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}, clear=True), \
                patch('urllib.request.urlopen', return_value=response(reply)) as send:
            call_model(judge, 'Grade this answer.')
        body = json.loads(send.call_args.args[0].data)
        self.assertEqual(body['model'], 'gpt-6-astra')
        self.assertEqual(body['reasoning_effort'], 'medium')
        self.assertEqual(body['max_completion_tokens'], 32768)
        self.assertNotIn('temperature', body)

    def test_rejects_incompatible_settings(self):
        astra = {'id': 'judge', 'provider': 'openai', 'model': 'gpt-6-astra'}
        invalid = [{**astra, 'reasoning_effort': 'none'},
                   {**astra, 'temperature': 0},
                   {**astra, 'reasoning_effort': 'medium', 'temperature': 0},
                   {**GEMINI, 'reasoning_effort': 'medium'},
                   {**GEMINI, 'timeout_seconds': True},
                   {**GEMINI, 'timeout_seconds': 0}]
        for model in invalid:
            with self.subTest(model=model), self.assertRaises(ValueError):
                validate_model(model)
        validate_model({**astra, 'model': 'gpt-6-luna', 'reasoning_effort': 'none', 'temperature': 0})

    def test_missing_gemini_key_fails_before_run_or_grade_artifacts(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {}, clear=True):
            root = Path(temp)
            config = root / 'config.json'
            config.write_text(json.dumps({'models': [GEMINI]}))
            dest = root / 'run'
            args = Namespace(dataset=ROOT / 'data/questions.csv', config=config, limit=1, out=dest, dry_run=False)
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, 'GEMINI_API_KEY'):
                run(args)
            self.assertFalse(dest.exists())
            judge = root / 'judge.json'
            judge.write_text(json.dumps(GEMINI))
            with self.assertRaisesRegex(ValueError, 'GEMINI_API_KEY'):
                grade(Namespace(run=dest, judge=judge))
            self.assertFalse(dest.exists())
            args.dry_run = True
            with contextlib.redirect_stdout(io.StringIO()) as printed, patch('urllib.request.urlopen') as send:
                run(args)
            self.assertIn('4 requests', printed.getvalue())
            send.assert_not_called()

    def test_gemini_to_astra_pipeline(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'GEMINI_API_KEY': 'gemini-test-secret', 'OPENAI_API_KEY': 'openai-test-secret'}, clear=True):
            root = Path(temp)
            config = root / 'config.json'
            config.write_text(json.dumps({'models': [GEMINI], 'conditions': ['neutral']}))
            dest = root / 'run'
            with contextlib.redirect_stdout(io.StringIO()), patch('urllib.request.urlopen', return_value=response(gemini_answer())):
                run(Namespace(dataset=ROOT / 'data/questions.csv', config=config, limit=1, out=dest, dry_run=False))
            record = json.loads((dest / 'responses.jsonl').read_text())
            self.assertEqual(record['returned_model'], 'gemini-returned-version')
            self.assertEqual(record['usage']['totalTokenCount'], 42)
            judgment = {'claims': [{'claim': 'Final answer.', 'label': 'unverifiable', 'rationale': 'Not supported by evidence.'}],
                        'answer_completeness': 'missing', 'agreement': 'not_applicable', 'tone': 'neutral', 'notes': ''}
            answer = {'model': 'gpt-6-astra', 'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(judgment)}}]}
            with contextlib.redirect_stdout(io.StringIO()), patch('urllib.request.urlopen', return_value=response(answer)) as send:
                grade(Namespace(run=dest, judge=ROOT / 'examples/judge.json'))
            judge_body = json.loads(send.call_args.args[0].data)
            self.assertEqual(judge_body['model'], 'gpt-6-astra')
            self.assertIn(record['response'], judge_body['messages'][0]['content'])
            grade_record = json.loads((dest / 'grades.jsonl').read_text())
            self.assertEqual(grade_record['status'], 'ok')
            self.assertEqual(grade_record['judge_returned_model'], 'gpt-6-astra')
            for path in dest.iterdir():
                if path.is_file():
                    self.assertNotIn('gemini-test-secret', path.read_text())
                    self.assertNotIn('openai-test-secret', path.read_text())


if __name__ == '__main__':
    unittest.main()
