"""Field file selection and metadata validation. Layout drafts may have 0/1 node."""
from pathlib import Path
import json
from .providers import MAP_PROVIDERS, provider_ids
from .terrain import number

from .paths import CONFIG_ROOT


def default_path():
    folder = CONFIG_ROOT / 'geography'
    catalog = json.loads((folder / 'catalog.json').read_text(encoding='utf-8'))
    return folder / catalog['default']


def check_field(raw):
    if not isinstance(raw, dict) or 'terrain' in raw:
        raise ValueError('Use an unprepared geographic config')
    geo = raw.get('geography')
    if not isinstance(geo, dict): raise ValueError('geography is required')
    number(geo.get('origin_lat'), 'origin_lat', -80, 80)
    number(geo.get('origin_lon'), 'origin_lon', -179, 179)
    map_id, _ = provider_ids(raw)
    ui = raw.get('planner', {})
    if 'field_name' in ui and (not isinstance(ui['field_name'], str) or not 1 <= len(ui['field_name'].strip()) <= 80):
        raise ValueError('Invalid field name')
    if 'view' in ui:
        v = ui['view']
        if not isinstance(v, dict): raise ValueError('Invalid field view')
        number(v.get('lat'), 'view.lat', -80, 80); number(v.get('lon'), 'view.lon', -179, 179)
        if type(v.get('zoom')) is not int or not 8 <= v['zoom'] <= 18: raise ValueError('Invalid view zoom')
        if v.get('layer') not in ('none', *MAP_PROVIDERS[map_id]['layers']): raise ValueError('Unsupported map layer')
    nodes = raw.get('nodes')
    if not isinstance(nodes, list) or len(nodes) > 20 or not isinstance(raw.get('messages'), list):
        raise ValueError('Expected 0..20 nodes and a messages array')
    # Incomplete/out-of-origin layouts can be edited; run validation remains strict.
    seen = set()
    for n in nodes:
        if not isinstance(n, dict) or type(n.get('id')) is not int or not 1 <= n['id'] <= 65534 or n['id'] in seen:
            raise ValueError('Invalid/duplicate node ID')
        seen.add(n['id']); number(n.get('lat'), 'lat', -80, 80); number(n.get('lon'), 'lon', -179, 179)
        number(n.get('antenna_m', 2), 'antenna_m', .1, 100)
    json.dumps(raw, allow_nan=False)
    return raw


def load_field(path=None):
    return check_field(json.loads(Path(path or default_path()).read_text(encoding='utf-8-sig')))
