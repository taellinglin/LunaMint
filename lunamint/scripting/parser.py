"""Parser for layout scripting."""
from __future__ import annotations
from typing import Any, List

from .ast import Disable, Enable, Program, SetValue, Use
from .lexer import Token, TokenType


class Parser:
    def __init__(self, tokens: List[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    def _peek(self) -> Token:
        return self.tokens[self.pos]

    def _advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _match(self, ttype: TokenType, value: str | None = None) -> Token:
        tok = self._peek()
        if tok.type != ttype or (value is not None and tok.value != value):
            raise ValueError(f"Expected {ttype} {value or ''} at {tok.line}:{tok.col}")
        return self._advance()

    def parse(self) -> Program:
        statements = []
        while self._peek().type != TokenType.EOF:
            if self._peek().type == TokenType.NEWLINE:
                self._advance()
                continue
            statements.append(self._statement())
        return Program(statements)

    def _statement(self):
        tok = self._match(TokenType.KEYWORD)
        if tok.value == "use":
            name = self._parse_ident_chain()
            return Use(name)
        if tok.value == "set":
            target = self._parse_ident_chain()
            self._match(TokenType.EQUAL)
            value = self._parse_value()
            return SetValue(target, value)
        if tok.value == "enable":
            name = self._parse_ident_chain()
            return Enable(name)
        if tok.value == "disable":
            name = self._parse_ident_chain()
            return Disable(name)
        raise ValueError(f"Unknown keyword {tok.value}")

    def _parse_ident_chain(self) -> str:
        parts = [self._match(TokenType.IDENT).value]
        while self._peek().type == TokenType.DOT:
            self._advance()
            parts.append(self._match(TokenType.IDENT).value)
        return ".".join(parts)

    def _parse_value(self) -> Any:
        tok = self._peek()
        if tok.type == TokenType.STRING:
            return self._advance().value
        if tok.type == TokenType.NUMBER:
            raw = self._advance().value
            return float(raw) if "." in raw else int(raw)
        if tok.type == TokenType.IDENT:
            return self._advance().value
        raise ValueError(f"Unexpected value at {tok.line}:{tok.col}")
