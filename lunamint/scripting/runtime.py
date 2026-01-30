"""Runtime compiler for layout scripts."""
from __future__ import annotations
from typing import Any, Dict

from .ast import Disable, Enable, Program, SetValue, Use
from .lexer import Lexer
from .parser import Parser


def compile_layout(source: str) -> Dict[str, Any]:
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    config: Dict[str, Any] = {
        "widgets": {},
        "filters": {},
        "values": {},
    }

    for stmt in program.statements:
        if isinstance(stmt, Use):
            config["widgets"].setdefault(stmt.name, True)
        elif isinstance(stmt, Enable):
            config["widgets"][stmt.name] = True
        elif isinstance(stmt, Disable):
            config["widgets"][stmt.name] = False
        elif isinstance(stmt, SetValue):
            config["values"][stmt.target] = stmt.value

    return config
