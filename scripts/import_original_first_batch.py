"""Import only the explicitly approved original-first milestone, with rollback."""
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    batch = json.loads((ROOT / 'expansion/batches/004-originals.json').read_text(encoding='utf-8'))
    path = ROOT / 'data/poems.json'
    assets = ROOT / 'app/assets/data/poems.json'
    source_before, assets_before = path.read_bytes(), assets.read_bytes()
    data = json.loads(source_before)
    by_id = {p['id']: p for p in data['items']}
    incoming = batch['items']
    existing = [p['id'] in by_id for p in incoming]
    if all(existing):
        if not all(by_id[p['id']] == p for p in incoming):
            raise ValueError('Existing milestone differs from saved batch')
        print('Original-first milestone already imported, unchanged.')
        return
    if any(existing) or len(data['items']) != 244 or len(incoming) != 356:
        raise ValueError('Unexpected base or colliding IDs')
    if batch.get('stage') != 'original_only':
        raise ValueError('Not an original-first batch')
    data['items'].extend(incoming)
    data['dataVersion'] = batch['dataVersion']
    if set(Counter(p['category'] for p in data['items']).values()) != {150}:
        raise ValueError('Milestone must contain exactly 150 of each category')
    encoded = (json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode('utf-8')
    try:
        path.write_bytes(encoded)
        assets.write_bytes(encoded)
        subprocess.run([sys.executable, str(ROOT/'scripts/validate_data.py'),
                        '--original-only', '--expected-per-category', '150'], check=True)
        subprocess.run([sys.executable, str(ROOT/'scripts/audit_expansion.py')], check=True)
    except BaseException:
        path.write_bytes(source_before)
        assets.write_bytes(assets_before)
        raise
    print('Imported 356 originals. Total 600; complete translations 244; pending 356.')


if __name__ == '__main__':
    main()
