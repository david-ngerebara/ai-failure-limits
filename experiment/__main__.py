import argparse
import csv
import hashlib
import json
import os
import random
import shutil
import sys
import uuid
from collections import defaultdict
from pathlib import Path

from .core import CONDITIONS, RUBRIC, call_model, judge_prompt, load_questions, now, parse_judgment, prompt_for, score, validate_model


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def jsonlines(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def csv_write(path, rows, fields):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def plan(args):
    rows = load_questions(args.dataset)
    config = read_json(args.config)
    if not isinstance(config, dict) or set(config) - {'models', 'conditions', 'repetitions', 'seed'}:
        raise ValueError('Config must contain only models, conditions, repetitions, and seed')
    models = config.get('models')
    conditions = config.get('conditions', list(CONDITIONS))
    repetitions = config.get('repetitions', 1)
    seed = config.get('seed', 42)
    if not isinstance(models, list) or not models:
        raise ValueError('At least one model is required')
    for model in models:
        validate_model(model)
    if len({m['id'] for m in models}) != len(models):
        raise ValueError('Model IDs must be unique')
    if not isinstance(conditions, list) or not conditions or any(c not in CONDITIONS for c in conditions) or len(set(conditions)) != len(conditions):
        raise ValueError('Conditions must be a nonempty list of unique supported conditions')
    if isinstance(repetitions, bool) or not isinstance(repetitions, int) or repetitions < 1:
        raise ValueError('repetitions must be a positive integer')
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError('seed must be an integer')
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError('limit must be positive')
        rows = rows[:args.limit]
    tasks = [(m, q, c, rep) for m in models for q in rows for c in conditions for rep in range(1, repetitions + 1)]
    random.Random(seed).shuffle(tasks)
    return rows, config, tasks


def run(args):
    rows, config, tasks = plan(args)
    missing = [r['question_id'] for r in rows if not r['source_url']]
    print(f'{len(rows)} questions × {len(config["models"])} models × {len(config.get("conditions", CONDITIONS))} conditions × {config.get("repetitions", 1)} repetitions = {len(tasks)} requests')
    if missing:
        print('WARNING: missing source URLs: ' + ', '.join(missing))
    if args.dry_run:
        for model, row, condition, rep in tasks:
            print(json.dumps({'model_id': model['id'], 'question_id': row['question_id'], 'condition': condition, 'repetition': rep, 'prompt': prompt_for(row, condition)}, ensure_ascii=False))
        return
    for model in config['models']:
        key = {'openai': 'OPENAI_API_KEY', 'anthropic': 'ANTHROPIC_API_KEY'}.get(model['provider'])
        if key and not os.environ.get(key):
            raise ValueError(f'{key} is not set for model {model["id"]}')
        if model['model'].startswith('REPLACE_'):
            raise ValueError(f'Replace the example model ID for {model["id"]}')
    dest = Path(args.out)
    dest.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(args.dataset, dest / 'questions.csv')
    write_json(dest / 'config.json', config)
    dataset_hash = hashlib.sha256((dest / 'questions.csv').read_bytes()).hexdigest()
    write_json(dest / 'manifest.json', {'created_at': now(), 'dataset_sha256': dataset_hash, 'question_ids': [r['question_id'] for r in rows], 'request_count': len(tasks), 'limit': args.limit, 'prompt_version': '1', 'run_id': dest.name})
    with (dest / 'responses.jsonl').open('w', encoding='utf-8') as out:
        for index, (model, row, condition, rep) in enumerate(tasks, 1):
            record = {**row, 'record_id': uuid.uuid4().hex, 'model_id': model['id'], 'provider': model['provider'], 'requested_model': model['model'], 'settings': {k: v for k, v in model.items() if k not in ('id', 'provider', 'model')}, 'condition': condition, 'repetition': rep, 'prompt': prompt_for(row, condition), 'started_at': now()}
            try:
                result = call_model(model, record['prompt'])
                record.update(status='ok', response=result['text'], returned_model=result['returned_model'], usage=result['usage'], error=None)
            except Exception as e:
                record.update(status='error', response=None, returned_model=None, usage={}, error=f'{type(e).__name__}: {e}')
            record['finished_at'] = now()
            out.write(json.dumps(record, ensure_ascii=False) + '\n')
            out.flush()
            print(f"[{index}/{len(tasks)}] {model['id']} {row['question_id']} {condition} #{rep}: {record['status']}", flush=True)


def grade(args):
    dest = Path(args.run)
    model = read_json(args.judge)
    validate_model(model)
    key = {'openai': 'OPENAI_API_KEY', 'anthropic': 'ANTHROPIC_API_KEY'}.get(model['provider'])
    if key and not os.environ.get(key):
        raise ValueError(f'{key} is not set for the judge')
    if model['model'].startswith('REPLACE_'):
        raise ValueError('Replace the example judge model ID')
    responses = jsonlines(dest / 'responses.jsonl')
    target = dest / 'grades.jsonl'
    if target.exists():
        raise ValueError('grades.jsonl already exists; preserve it and use a copy of the run to regrade')
    write_json(dest / 'judge_config.json', model)
    (dest / 'rubric.txt').write_text(RUBRIC + '\n', encoding='utf-8')
    with target.open('x', encoding='utf-8') as out:
        for i, rec in enumerate(responses, 1):
            result = {'record_id': rec['record_id'], 'judge_model_id': model['id'], 'judge_provider': model['provider'], 'judge_requested_model': model['model'], 'started_at': now()}
            if rec['status'] != 'ok':
                result.update(status='skipped', error='Response collection failed')
            else:
                try:
                    if model['provider'] == 'mock':
                        # Explicitly a pipeline fixture, never a simulated factuality result.
                        raw = json.dumps({'claims': [], 'answer_completeness': 'unclear', 'agreement': 'unclear', 'tone': 'not evaluated', 'notes': 'Offline fixture; not a real evaluation.'})
                        returned = model['model']
                        usage = {}
                    else:
                        result['judge_prompt'] = judge_prompt(rec)
                        reply = call_model(model, result['judge_prompt'])
                        raw, returned, usage = reply['text'], reply['returned_model'], reply['usage']
                    result.update(raw_judgment=raw, judge_returned_model=returned, usage=usage)
                    result.update(status='ok', judgment=parse_judgment(raw), error=None)
                except Exception as e:
                    result.update(status='error', error=f'{type(e).__name__}: {e}')
            result['finished_at'] = now()
            out.write(json.dumps(result, ensure_ascii=False) + '\n')
            out.flush()
            print(f"[{i}/{len(responses)}] {rec['record_id']}: {result['status']}", flush=True)


def report(args):
    dest = Path(args.run)
    responses = jsonlines(dest / 'responses.jsonl')
    grades = jsonlines(dest / 'grades.jsonl')
    manifest = read_json(dest / 'manifest.json')
    if len(responses) != manifest['request_count']:
        print(f"WARNING: run is incomplete: {len(responses)} of {manifest['request_count']} planned responses recorded", file=sys.stderr)
    if len(grades) != len(responses):
        print(f"WARNING: grading is incomplete: {len(grades)} of {len(responses)} responses have grade records", file=sys.stderr)
    by_id = {g['record_id']: g for g in grades}
    if len(by_id) != len(grades):
        raise ValueError('Duplicate grade record IDs')
    rows = []
    for r in responses:
        g = by_id.get(r['record_id'], {})
        row = {k: r.get(k) for k in ('record_id', 'question_id', 'topic', 'difficulty', 'question_type', 'model_id', 'provider', 'requested_model', 'returned_model', 'condition', 'repetition', 'prompt', 'response')}
        row.update(response_status=r['status'], grade_status=g.get('status', 'missing'), error=r.get('error') or g.get('error'))
        if g.get('status') == 'ok':
            j = g['judgment']
            row.update(score(j), answer_completeness=j['answer_completeness'], agreement=j['agreement'], tone=j['tone'], grade_notes=j['notes'])
        rows.append(row)
    fields = ['record_id', 'question_id', 'topic', 'difficulty', 'question_type', 'model_id', 'provider', 'requested_model', 'returned_model', 'condition', 'repetition', 'response_status', 'grade_status', 'supported', 'contradicted', 'unverifiable', 'claim_count', 'factuality', 'answer_completeness', 'agreement', 'tone', 'grade_notes', 'error', 'prompt', 'response']
    csv_write(dest / 'results.csv', rows, fields)
    groups = defaultdict(list)
    for row in rows:
        groups[(row['model_id'], row['condition'], row['difficulty'])].append(row)
    summaries = []
    for (model, condition, difficulty), items in sorted(groups.items()):
        scored = [x['factuality'] for x in items if x.get('factuality') is not None]
        summaries.append({'model_id': model, 'condition': condition, 'difficulty': difficulty, 'responses': len(items), 'response_errors': sum(x['response_status'] != 'ok' for x in items), 'grade_errors_or_missing': sum(x['response_status'] == 'ok' and x['grade_status'] != 'ok' for x in items), 'zero_claims': sum(x.get('claim_count') == 0 for x in items), 'scored': len(scored), 'mean_factuality': sum(scored) / len(scored) if scored else None, 'supported': sum(x.get('supported', 0) for x in items), 'contradicted': sum(x.get('contradicted', 0) for x in items), 'unverifiable': sum(x.get('unverifiable', 0) for x in items)})
    csv_write(dest / 'summary.csv', summaries, ['model_id', 'condition', 'difficulty', 'responses', 'response_errors', 'grade_errors_or_missing', 'zero_claims', 'scored', 'mean_factuality', 'supported', 'contradicted', 'unverifiable'])
    neutral = {(r['model_id'], r['question_id'], r['repetition']): r for r in rows if r['condition'] == 'neutral'}
    paired = []
    for row in rows:
        if row['condition'] == 'neutral':
            continue
        base = neutral.get((row['model_id'], row['question_id'], row['repetition']))
        if base and base.get('factuality') is not None and row.get('factuality') is not None:
            paired.append({'model_id': row['model_id'], 'question_id': row['question_id'], 'difficulty': row['difficulty'], 'repetition': row['repetition'], 'condition': row['condition'], 'neutral_record_id': base['record_id'], 'condition_record_id': row['record_id'], 'neutral_factuality': base['factuality'], 'condition_factuality': row['factuality'], 'delta': row['factuality'] - base['factuality']})
    csv_write(dest / 'paired.csv', paired, ['model_id', 'question_id', 'difficulty', 'repetition', 'condition', 'neutral_record_id', 'condition_record_id', 'neutral_factuality', 'condition_factuality', 'delta'])
    # All rows are reviewable; an independent sample can be selected before comparisons.
    review = [{**r, 'human_factuality_notes': '', 'human_agreement': '', 'human_tone': '', 'human_completeness': '', 'reviewer': ''} for r in rows]
    review_path = dest / 'review.csv'
    if not review_path.exists():
        csv_write(review_path, review, fields + ['human_factuality_notes', 'human_agreement', 'human_tone', 'human_completeness', 'reviewer'])
        review_message = 'created review.csv'
    else:
        review_message = 'preserved existing review.csv'
    print(f'Wrote results.csv, summary.csv, paired.csv ({len(paired)} pairs); {review_message}')


def main():
    parser = argparse.ArgumentParser(description='Run and evaluate AI framing experiments')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('run', help='Validate or collect responses')
    p.add_argument('--dataset', default='data/questions.csv')
    p.add_argument('--config', required=True)
    p.add_argument('--out', help='New run directory; required unless --dry-run')
    p.add_argument('--limit', type=int, help='Use first N dataset rows for a pilot')
    p.add_argument('--dry-run', action='store_true')
    p.set_defaults(func=run)
    p = sub.add_parser('grade', help='Evaluate collected responses')
    p.add_argument('--run', required=True)
    p.add_argument('--judge', required=True)
    p.set_defaults(func=grade)
    p = sub.add_parser('report', help='Create CSVs for analysis and review')
    p.add_argument('--run', required=True)
    p.set_defaults(func=report)
    args = parser.parse_args()
    if args.command == 'run' and not args.dry_run and not args.out:
        parser.error('--out is required without --dry-run')
    try:
        args.func(args)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as e:
        print(f'Error: {e}', file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
