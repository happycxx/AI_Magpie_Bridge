"""File I/O helpers."""
import os
import json


def read_file_content(file_path):
    """Read file content with utf-8 encoding. Raises on failure."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def write_file_content(file_path, content):
    """Write content to file with utf-8 encoding. Raises on failure."""
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)


def ensure_dir(dir_path):
    """Create directory if it doesn't exist."""
    os.makedirs(dir_path, exist_ok=True)


def load_json(file_path, default=None):
    """Load JSON from file, returning default on any failure."""
    if not os.path.exists(file_path):
        return default
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def save_json(file_path, data):
    """Save data as JSON with utf-8 encoding."""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def get_app_dir():
    """Return the application root directory."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
