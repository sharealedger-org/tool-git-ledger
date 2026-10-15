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


def _parse_simple_yaml(text: str) -> Any:
    """
    Minimal parser for simple YAML when PyYAML is not installed.

    Handles two top-level structures:
    - A list of dicts (``- key: value`` items) — used by journal/accounts files.
    - A plain dict (``key: value`` or ``key:\\n  subkey: value``) — used by
      mapping-rules files.

    Nested dicts are supported up to two levels deep.  Multi-line values and
    YAML anchors/aliases are not supported.
    """
    lines = text.splitlines()

    # Determine top-level structure by looking at the first non-comment,
    # non-empty line.
    first_content = next(
        (l.strip() for l in lines if l.strip() and not l.strip().startswith("#")),
        "",
    )
    if first_content.startswith("- "):
        return _parse_yaml_list(lines)
    return _parse_yaml_dict(lines)


def _parse_yaml_list(lines: list) -> list:
    """Parse a top-level list-of-dicts YAML document."""
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
                    current_list_key = k
                    current_item[k] = []
                elif current_sub_item is not None and indent >= 6:
                    current_sub_item[k] = _parse_scalar(v)
                else:
                    current_item[k] = _parse_scalar(v)

    if current_item is not None:
        items.append(current_item)
    return items


def _parse_yaml_dict(lines: list) -> dict:
    """
    Parse a top-level dict YAML document with optional one-level-deep nested
    dicts (indented sub-keys).  Supports quoted keys to handle strings like
    ``"Bank Service Charges": "5400"``.
    """
    result: dict = {}
    current_key: str | None = None  # current top-level key whose value is a dict

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip())

        # Quoted or unquoted key: value
        if ":" in stripped:
            # Split on first colon not inside quotes
            colon_pos = _find_colon(stripped)
            if colon_pos == -1:
                continue
            raw_k = stripped[:colon_pos].strip().strip('"').strip("'")
            raw_v = _strip_inline_comment(stripped[colon_pos + 1:].strip()).strip('"').strip("'")

            if indent == 0:
                # Top-level key
                if raw_v:
                    result[raw_k] = _parse_scalar(raw_v)
                    current_key = None
                else:
                    # Key with no value — nested dict follows
                    result[raw_k] = {}
                    current_key = raw_k
            else:
                # Indented — belongs to current_key's dict
                if current_key is not None:
                    result[current_key][raw_k] = _parse_scalar(raw_v) if raw_v else {}

    return result


def _strip_inline_comment(s: str) -> str:
    """Remove a trailing ``# comment`` from a YAML value, respecting quotes."""
    in_single = False
    in_double = False
    for i, ch in enumerate(s):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return s[:i].rstrip()
    return s


def _find_colon(s: str) -> int:
    """Return index of the first colon in *s* that is not inside quotes."""
    in_single = False
    in_double = False
    for i, ch in enumerate(s):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == ":" and not in_single and not in_double:
            return i
    return -1


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
