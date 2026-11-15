"""Load provider keys from a local .env file without executing or expanding it."""
import os
import re
from pathlib import Path

from .core import API_KEY_ENV


def load_api_keys(path, required=False):
    path = Path(path)
    if not path.exists() and not required:
        return
    keys = {}
    for line_number, raw in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].lstrip()
        name, separator, value = line.partition('=')
        name, value = name.strip(), value.strip()
        if not separator or name not in API_KEY_ENV.values():
            raise ValueError(f'Invalid API key entry on line {line_number} of {path.name}; use a supported KEY=value entry')
        if value.startswith(('"', "'")):
            quote = value[0]
            end = value.find(quote, 1)
            if end < 0 or (value[end + 1:].strip() and not value[end + 1:].strip().startswith('#')):
                raise ValueError(f'Invalid quoted API key on line {line_number} of {path.name}')
            value = value[1:end]
        else:
            value = re.split(r'\s+#', value, maxsplit=1)[0].strip()
        if name in keys:
            raise ValueError(f'Duplicate API key entry on line {line_number} of {path.name}')
        keys[name] = value
    # Parse the whole file first so invalid input never partially changes the environment.
    for name, value in keys.items():
        if value:
            os.environ.setdefault(name, value)
