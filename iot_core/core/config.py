from pathlib import Path
import yaml

SETTINGS_PATH = Path(__file__).resolve().parents[2] / "config" / "settings.yaml"

def load_config():
    return yaml.safe_load(SETTINGS_PATH.read_text())
