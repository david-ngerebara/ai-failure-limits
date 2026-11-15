import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiment.__main__ import main
from experiment.secrets import load_api_keys

ROOT = Path(__file__).resolve().parents[1]


class SecretsTests(unittest.TestCase):
    def test_loading_and_environment_precedence(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'OPENAI_API_KEY': 'shell-value'}, clear=True):
            path = Path(temp) / '.env'
            path.write_text('# comment\nOPENAI_API_KEY=file-value\nexport ANTHROPIC_API_KEY="quoted-value" # note\nGEMINI_API_KEY=raw#value # note\n')
            load_api_keys(path)
            self.assertEqual(os.environ['OPENAI_API_KEY'], 'shell-value')
            self.assertEqual(os.environ['ANTHROPIC_API_KEY'], 'quoted-value')
            self.assertEqual(os.environ['GEMINI_API_KEY'], 'raw#value')

    def test_empty_and_missing_files(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {}, clear=True):
            path = Path(temp) / '.env'
            load_api_keys(path)
            with self.assertRaises(FileNotFoundError):
                load_api_keys(path, required=True)
            path.write_text('OPENAI_API_KEY=\nANTHROPIC_API_KEY=""\nGEMINI_API_KEY=\n')
            load_api_keys(path)
            self.assertEqual(dict(os.environ), {})

    def test_invalid_file_is_atomic_and_errors_do_not_reveal_keys(self):
        for bad_line in ['WRONG_KEY=secret-value', 'OPENAI_API_KEY="secret-value', 'OPENAI_API_KEY=secret-value']:
            with self.subTest(line=bad_line), tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {}, clear=True):
                path = Path(temp) / '.env'
                path.write_text('OPENAI_API_KEY=valid-value\n' + bad_line + '\n')
                with self.assertRaises(ValueError) as raised:
                    load_api_keys(path)
                self.assertNotIn('secret-value', str(raised.exception))
                self.assertNotIn('valid-value', str(raised.exception))
                self.assertEqual(dict(os.environ), {})

    def test_shell_syntax_is_literal(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {}, clear=True):
            path = Path(temp) / '.env'
            path.write_text("OPENAI_API_KEY='$(touch never-run)${HOME}'\n")
            load_api_keys(path)
            self.assertEqual(os.environ['OPENAI_API_KEY'], '$(touch never-run)${HOME}')

    def test_cli_uses_explicit_secrets_file(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {}, clear=True):
            root = Path(temp)
            secrets = root / 'private.env'
            secrets.write_text('GEMINI_API_KEY=local-test-key\n')
            config = root / 'config.json'
            config.write_text(json.dumps({'models': [{'id': 'gemini', 'provider': 'gemini', 'model': 'gemini-4-hydrogen'}], 'conditions': ['neutral']}))
            argv = ['experiment', '--env-file', str(secrets), 'run', '--dataset', str(ROOT / 'data/questions.csv'), '--config', str(config), '--limit', '1', '--out', str(root / 'run')]
            payload = {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': 'A response.'}]}}]}
            with patch('sys.argv', argv), contextlib.redirect_stdout(io.StringIO()), \
                    patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(payload).encode())) as send:
                self.assertEqual(main(), 0)
            self.assertEqual(send.call_args.args[0].get_header('X-goog-api-key'), 'local-test-key')


if __name__ == '__main__':
    unittest.main()
