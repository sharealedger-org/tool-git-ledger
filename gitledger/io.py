"""
File I/O helpers supporting YAML and JSON with zero required dependencies.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def load_data_file(path: Path) -> Any:
    """Loads data from a .yaml, .yml, or .json file."""
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return []

    if HAS_YAML:
        return yaml.safe_load(content)

    # If PyYAML is not installed, try JSON parsing
    if content.startswith("{") or content.startswith("["):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

    # Fallback minimal YAML list-of-dicts parser
    return _parse_simple_yaml(content)


def save_data_file(data: Any, path: Path):
    """Saves data to a .yaml or .json file."""
    if path.suffix == ".json":
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return

    if HAS_YAML:
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, sort_keys=False, default_flow_style=False)
    else:
        # Save formatted JSON if yaml is not installed
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _parse_simple_yaml(text: str) -> list:
    """
    Minimal parser for simple list-of-dicts YAML when PyYAML is not installed.
    """
    lines = text.splitlines()
    items = []
    current_item = None
    current_list_key = None
    current_sub_item = None

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip())

        # Top-level item starting with "- "
        if line.startswith("- "):
            if current_item is not None:
                items.append(current_item)
            current_item = {}
            current_list_key = None
            current_sub_item = None
            rest = line[2:].strip()
            if ":" in rest:
                k, v = rest.split(":", 1)
                current_item[k.strip()] = _parse_scalar(v.strip())
        elif current_item is not None:
            # Check for sub-list item like "    - account: '1010'"
            if stripped.startswith("- "):
                sub_rest = stripped[2:].strip()
                current_sub_item = {}
                if current_list_key and isinstance(current_item.get(current_list_key), list):
                    current_item[current_list_key].append(current_sub_item)
                if ":" in sub_rest:
                    sk, sv = sub_rest.split(":", 1)
                    current_sub_item[sk.strip()] = _parse_scalar(sv.strip())
            elif ":" in stripped:
                k, v = stripped.split(":", 1)
                k = k.strip()
                v = v.strip()
                if not v:
                    # New sublist key like "entries:"
                    current_list_key = k
                    current_item[k] = []
                elif current_sub_item is not None and indent >= 6:
                    current_sub_item[k] = _parse_scalar(v)
                else:
                    current_item[k] = _parse_scalar(v)

    if current_item is not None:
        items.append(current_item)
    return items


def _parse_scalar(val: str) -> Any:
    val = val.strip()
    if (val.startswith("'") and val.endswith("'")) or (val.startswith('"') and val.endswith('"')):
        return val[1:-1]
    if val.lower() == "true":
        return True
    if val.lower() == "false":
        return False
    if val.lower() == "null" or val == "":
        return None
    try:
        if "." in val:
            return float(val)
        return int(val)
    except ValueError:
        return val
