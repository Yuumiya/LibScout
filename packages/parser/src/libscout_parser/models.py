from __future__ import annotations

from dataclasses import dataclass

from tree_sitter import Node, Tree


class ParseError(Exception):
    """Raised when parsing a file or source code fails."""


class UnsupportedLanguageError(ParseError):
    """Raised when the language cannot be detected or is not supported."""


@dataclass(eq=False)
class ParseResult:
    """Result of parsing a source file into a concrete syntax tree."""

    source_path: str
    language: str
    tree: Tree
    source: bytes

    @property
    def root_node(self) -> Node:
        """Return the root node of the parsed tree."""
        return self.tree.root_node

    @property
    def s_expression(self) -> str:
        """Return an S-expression string representation of the CST."""
        return str(self.tree.root_node)
