"""Data-provider boundary. Only GSI is implemented in v0.6.
Map descriptors are trusted local code, not URLs supplied by a Field Config.
"""
from typing import Protocol

DEFAULT_MAP = 'gsi'
DEFAULT_DEM = 'gsi_dem'
MAP_PROVIDERS = {
    'gsi': {
        'label': '国土地理院・地理院地図',
        'tile_base': 'https://cyberjapandata.gsi.go.jp/xyz',
        'attribution': '出典：国土地理院（地理院タイル）',
        'attribution_url': 'https://maps.gsi.go.jp/development/ichiran.html',
        'layers': {
            'std': {'label': '標準地図', 'ext': 'png', 'max_zoom': 18},
            'pale': {'label': '淡色地図', 'ext': 'png', 'max_zoom': 18},
            'relief': {'label': '色別標高図', 'ext': 'png', 'max_zoom': 15,
                       'extra_attribution': ' ／ 海域部は海上保安庁海洋情報部の資料を使用して作成'},
            'seamlessphoto': {'label': '航空写真', 'ext': 'jpg', 'max_zoom': 18,
                              'extra_attribution': ' ／ 国土地理院・写真提供機関の出典はタイル一覧参照'},
        },
    },
}
DEM_PROVIDERS = {'gsi_dem': '国土地理院 DEM'}

class ElevationProvider(Protocol):
    def sample(self, lat: float, lon: float) -> float: ...


def map_provider_id(raw):
    ui = raw.get('planner', {})
    if not isinstance(ui, dict): raise ValueError('Invalid planner settings')
    value = ui.get('map_provider', DEFAULT_MAP)
    if not isinstance(value, str) or value not in MAP_PROVIDERS:
        raise ValueError('Unsupported map provider')
    return value


def dem_provider_id(raw):
    geo = raw.get('geography', {})
    if not isinstance(geo, dict): raise ValueError('Invalid geography settings')
    value = geo.get('dem_provider', DEFAULT_DEM)
    if not isinstance(value, str) or value not in DEM_PROVIDERS:
        raise ValueError('Unsupported DEM provider')
    return value


def provider_ids(raw):
    return map_provider_id(raw), dem_provider_id(raw)


def create_dem(provider_id, cache, offline=False):
    if provider_id == 'gsi_dem':
        from .dem_gsi import GsiDEM
        return GsiDEM(cache, offline)
    raise ValueError('Unsupported DEM provider')
