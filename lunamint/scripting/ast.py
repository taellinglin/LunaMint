"""AST nodes for the layout scripting language."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, List


@dataclass
class Node:
    pass


@dataclass
class Program(Node):
    statements: List[Node]


@dataclass
class Use(Node):
    name: str


@dataclass
class SetValue(Node):
    target: str
    value: Any


@dataclass
class Enable(Node):
    name: str


@dataclass
class Disable(Node):
    name: str
