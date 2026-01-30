"""Lexer for layout scripting."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import List


class TokenType(Enum):
    IDENT = auto()
    STRING = auto()
    NUMBER = auto()
    EQUAL = auto()
    DOT = auto()
    NEWLINE = auto()
    EOF = auto()
    KEYWORD = auto()


KEYWORDS = {"use", "set", "enable", "disable"}


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    col: int


class Lexer:
    def __init__(self, source: str) -> None:
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1

    def _peek(self) -> str:
        if self.pos >= len(self.source):
            return ""
        return self.source[self.pos]

    def _advance(self) -> str:
        ch = self._peek()
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def tokenize(self) -> List[Token]:
        tokens: List[Token] = []
        while True:
            ch = self._peek()
            if ch == "":
                tokens.append(Token(TokenType.EOF, "", self.line, self.col))
                break
            if ch in " \t\r":
                self._advance()
                continue
            if ch == "#":
                self._skip_comment()
                continue
            if ch == "\n":
                tokens.append(Token(TokenType.NEWLINE, "\n", self.line, self.col))
                self._advance()
                continue
            if ch == "=":
                tokens.append(Token(TokenType.EQUAL, "=", self.line, self.col))
                self._advance()
                continue
            if ch == ".":
                tokens.append(Token(TokenType.DOT, ".", self.line, self.col))
                self._advance()
                continue
            if ch == '"' or ch == "'":
                tokens.append(self._string())
                continue
            if ch.isdigit():
                tokens.append(self._number())
                continue
            if ch.isalpha() or ch == "_":
                tokens.append(self._ident())
                continue
            raise ValueError(f"Unexpected char '{ch}' at {self.line}:{self.col}")
        return tokens

    def _string(self) -> Token:
        quote = self._advance()
        start_line, start_col = self.line, self.col
        value = ""
        while True:
            ch = self._peek()
            if ch == "":
                raise ValueError("Unterminated string")
            if ch == quote:
                self._advance()
                break
            value += self._advance()
        return Token(TokenType.STRING, value, start_line, start_col)

    def _number(self) -> Token:
        start_line, start_col = self.line, self.col
        value = ""
        while self._peek().isdigit() or self._peek() == ".":
            value += self._advance()
        return Token(TokenType.NUMBER, value, start_line, start_col)

    def _ident(self) -> Token:
        start_line, start_col = self.line, self.col
        value = ""
        while self._peek().isalnum() or self._peek() == "_":
            value += self._advance()
        if value in KEYWORDS:
            return Token(TokenType.KEYWORD, value, start_line, start_col)
        return Token(TokenType.IDENT, value, start_line, start_col)

    def _skip_comment(self) -> None:
        while self._peek() not in ("", "\n"):
            self._advance()
