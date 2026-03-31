from __future__ import annotations

from pathlib import Path

from tree_sitter_language_pack import get_parser

from .detector import detect_language
from .models import ParseError, ParseResult, UnsupportedLanguageError


def parse_file(path: str | Path, *, language: str | None = None) -> ParseResult:
    """Read a file from disk and parse it into a concrete syntax tree.

    If *language* is not provided, it is auto-detected from the file path.

    Raises:
        ParseError: If the file cannot be read.
        UnsupportedLanguageError: If the language cannot be detected or is not supported.
    """
    file_path = Path(path)

    try:
        source = file_path.read_bytes()
    except OSError as exc:
        raise ParseError(f"Failed to read file: {file_path}: {exc}") from exc

    if language is None:
        language = detect_language(str(file_path))

    try:
        parser = get_parser(language)  # pyright: ignore[reportArgumentType]
    except Exception as exc:
        raise UnsupportedLanguageError(f"Failed to get parser for language {language!r}: {exc}") from exc

    tree = parser.parse(source)

    return ParseResult(source_path=str(file_path), language=language, tree=tree, source=source)


def parse_code(source: bytes | str, *, language: str) -> ParseResult:
    """Parse source code with an explicitly specified language.

    The ``source_path`` in the returned :class:`ParseResult` is ``"<string>"``.

    Raises:
        UnsupportedLanguageError: If the language is not supported.
        ParseError: If parsing fails.
    """
    source_bytes = source.encode("utf-8") if isinstance(source, str) else source

    try:
        parser = get_parser(language)  # pyright: ignore[reportArgumentType]
    except Exception as exc:
        raise UnsupportedLanguageError(f"Failed to get parser for language {language!r}: {exc}") from exc

    tree = parser.parse(source_bytes)

    return ParseResult(source_path="<string>", language=language, tree=tree, source=source_bytes)
