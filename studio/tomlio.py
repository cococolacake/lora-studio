"""Tiny TOML writer for sd-scripts configs (reading uses the stdlib tomllib)."""
import json
import re

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10: same parser, installed as 'tomli'
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        tomllib = None


def _value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        r = repr(v)
        return r if ("." in r or "e" in r or "inf" in r or "nan" in r) else r + ".0"
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_value(x) for x in v) + "]"
    if isinstance(v, str):
        return json.dumps(v.replace("\\", "/") if _looks_like_path(v) else v, ensure_ascii=False)
    raise TypeError(f"Can't write {type(v).__name__} to TOML")


def _looks_like_path(s):
    return bool(re.match(r"^[A-Za-z]:\\", s)) or ("\\" in s and "/" not in s and " " not in s.strip())


def _key(k):
    return k if re.fullmatch(r"[A-Za-z0-9_-]+", k) else json.dumps(k)


def dumps(data):
    """Write a dict. Nested dicts become [tables]; lists of dicts become [[arrays of tables]]."""
    lines = []
    _write_table(lines, data, [])
    return "\n".join(lines).strip() + "\n"


def _write_table(lines, table, path):
    scalars = {k: v for k, v in table.items()
               if v is not None and not isinstance(v, dict) and not _is_table_array(v)}
    for k, v in scalars.items():
        lines.append(f"{_key(k)} = {_value(v)}")
    for k, v in table.items():
        if isinstance(v, dict):
            lines.append("")
            lines.append("[" + ".".join(_key(p) for p in path + [k]) + "]")
            _write_table(lines, v, path + [k])
        elif _is_table_array(v):
            for item in v:
                lines.append("")
                lines.append("[[" + ".".join(_key(p) for p in path + [k]) + "]]")
                _write_table(lines, item, path + [k])


def _is_table_array(v):
    return isinstance(v, list) and v and all(isinstance(x, dict) for x in v)


def loads(text):
    if tomllib is None:
        raise RuntimeError("Reading TOML needs Python 3.11+, or `pip install tomli` on 3.10.")
    return tomllib.loads(text)


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return loads(f.read())


def coerce(kind, raw):
    """Turn a form value (string/bool from the UI) into a typed TOML value, or None to omit."""
    if kind in ("bool", "bool_false"):
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    if raw is None:
        return None
    if isinstance(raw, (list, int, float)) and not isinstance(raw, bool):
        return raw
    s = str(raw).strip()
    if s == "":
        return None
    if kind == "int":
        try:
            return int(float(s))
        except ValueError:
            return s
    if kind == "float":
        try:
            return float(s)
        except ValueError:
            return s
    if kind == "number":   # whole number or decimal, e.g. lr_warmup_steps = 100 or 0.1
        try:
            f = float(s)
        except ValueError:
            return s
        return int(f) if f.is_integer() and not any(c in s for c in ".eE") else f
    if kind == "list":
        if s.startswith("["):
            try:
                return json.loads(s)
            except ValueError:
                pass
        return [p for p in (s.split("\n") if "\n" in s else _split_list(s)) if p]
    return s


def _split_list(s):
    """'a=1 b="x y"' -> ['a=1', 'b=x y'] ; also accepts comma separation."""
    import shlex
    try:
        parts = shlex.split(s, posix=True)
    except ValueError:
        parts = s.split()
    if len(parts) == 1 and "," in parts[0] and "=" not in parts[0]:
        parts = [p.strip() for p in parts[0].split(",")]
    return parts
