"""Shared definition of stored entries and the user-visible active library."""
def disabled_ids(data):
    entries = data.get('disabledEntries', [])
    all_ids = {p['id'] for p in data['items']}
    ids = [p['id'] for p in entries]
    if len(ids) != len(set(ids)) or not set(ids) <= all_ids:
        raise ValueError('Duplicate or unknown disabled ID')
    for entry in entries:
        if not entry.get('reason') or entry.get('replacementId') not in all_ids:
            raise ValueError('Disabled entry needs a reason and existing replacement')
        if entry['replacementId'] in ids:
            raise ValueError('Replacement must be active')
    return set(ids)


def active_items(data):
    excluded = disabled_ids(data)
    profile = data.get('selectionProfile')
    selected = None
    if profile is not None:
        ids = profile['ids']
        selected = set(ids)
        stored = {p['id'] for p in data['items']}
        if len(ids) != len(selected) or not selected <= stored or selected & excluded:
            raise ValueError('Invalid selected library IDs')
    return [p for p in data['items'] if p['id'] not in excluded and
            (selected is None or p['id'] in selected)]
