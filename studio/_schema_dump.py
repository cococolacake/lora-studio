"""Runs INSIDE the sd-scripts venv: prints every argparse option of one training script as JSON.

Usage: python _schema_dump.py <sd-scripts dir> <script.py>
Kept dependency-free and Python 3.10 compatible on purpose.
"""
import argparse
import importlib.util
import io
import json
import os
import sys


def jsonable(v):
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    return str(v)


def kind_of(action):
    name = type(action).__name__
    if name in ("_StoreTrueAction", "BooleanOptionalAction"):
        return "bool"
    if name == "_StoreFalseAction":
        return "bool_false"
    if action.nargs in ("*", "+") or isinstance(action.nargs, int) or name == "_AppendAction":
        return "list"
    t = getattr(action.type, "__name__", None)
    if t in ("int", "float"):
        return t
    return "str"


def english_help(action):
    """sd-scripts help is usually 'English text / 日本語テキスト'; keep the English half."""
    h = action.help or ""
    if h == argparse.SUPPRESS:
        return ""
    h = h.replace("%(default)s", str(action.default))
    if " / " in h:
        first, rest = h.split(" / ", 1)
        if any(ord(ch) > 0x2E80 for ch in rest):
            h = first
    return h.strip()


def main():
    repo, script = sys.argv[1], sys.argv[2]
    os.chdir(repo)
    sys.path.insert(0, repo)
    sys.argv = [script]
    real_stdout = sys.stdout
    sys.stdout = io.StringIO()  # swallow anything printed while importing torch & friends
    try:
        spec = importlib.util.spec_from_file_location("lora_studio_target", os.path.join(repo, script))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if not hasattr(mod, "setup_parser"):
            raise SystemExit(f"{script} has no setup_parser()")
        parser = mod.setup_parser()
    finally:
        sys.stdout = real_stdout

    group_of = {}
    for g in parser._action_groups:
        for a in g._group_actions:
            group_of[id(a)] = g.title

    out = []
    for a in parser._actions:
        if isinstance(a, argparse._HelpAction) or not a.option_strings:
            continue
        long_opt = next((o for o in a.option_strings if o.startswith("--")), a.option_strings[0])
        out.append({
            "key": a.dest,
            "flag": long_opt,
            "kind": kind_of(a),
            "default": jsonable(a.default),
            "choices": jsonable(list(a.choices)) if a.choices else None,
            "help": english_help(a),
            "required": bool(a.required),
            "group": group_of.get(id(a)) or "options",
        })
    print("<<<SCHEMA>>>" + json.dumps({"script": script, "args": out}) + "<<<END>>>")


if __name__ == "__main__":
    main()
