"""Repository and bundled resource locations (no installation required)."""
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
ROOT = PACKAGE_ROOT.parent
CONFIG_ROOT = ROOT / 'configs'
WEB_ROOT = PACKAGE_ROOT / 'web'
