"""Scripts that run INSIDE the sd-scripts venv (where torch lives).

They talk back to LoRA Studio by printing lines:
    @@P {"n": 3, "total": 40, "msg": "..."}   progress
    @@R {...}                                 final result
    @@MISSING timm                            a Python package isn't installed in that venv
Keep them Python 3.10 compatible and free of LoRA Studio imports.
"""
