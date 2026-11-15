"""Optional plots, using per-response scores and within-question paired differences."""
import csv
import sys
from collections import defaultdict
from pathlib import Path


def main(directory):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        raise SystemExit('Install matplotlib to create plots: python -m pip install matplotlib')
    dest = Path(directory)
    with (dest / 'results.csv').open(encoding='utf-8', newline='') as f:
        results = list(csv.DictReader(f))
    with (dest / 'paired.csv').open(encoding='utf-8', newline='') as f:
        paired = list(csv.DictReader(f))
    def chart(rows, field, title, filename, ylabel):
        grouped = defaultdict(list)
        for row in rows:
            if row.get(field) not in (None, ''):
                grouped[(row['model_id'], row['condition'])].append(float(row[field]))
        if not grouped:
            print(f'No scored data for {filename}; skipped')
            return
        keys = sorted(grouped)
        fig, ax = plt.subplots(figsize=(max(6, len(keys) * 1.2), 5))
        ax.bar(range(len(keys)), [sum(grouped[k])/len(grouped[k]) for k in keys])
        ax.set_xticks(range(len(keys)), [f'{m}\n{c}\n(n={len(grouped[(m,c)])})' for m, c in keys], rotation=25, ha='right')
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.axhline(0, color='black', linewidth=.7)
        fig.tight_layout()
        fig.savefig(dest / filename, dpi=160)
        plt.close(fig)
    chart(results, 'factuality', 'Average factuality by model and condition', 'factuality.png', 'Mean score (0–100)')
    chart(paired, 'delta', 'Paired change relative to neutral', 'paired-delta.png', 'Mean score difference (points)')

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python -m experiment.plot RUN_DIRECTORY')
    main(sys.argv[1])
