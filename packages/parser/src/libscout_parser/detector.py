from __future__ import annotations

from tree_sitter_language_pack import detect_language as _detect_language
from tree_sitter_language_pack import get_parser

from .models import UnsupportedLanguageError


def detect_language(path: str) -> str:
    """Detect the programming language of a file by its path/extension.

    Uses ``tree_sitter_language_pack.detect_language`` under the hood.

    Parameters
    ----------
    path:
        A file path (or just a filename with extension) to detect the language for.

    Returns
    -------
    str
        The detected language name recognised by tree-sitter-language-pack.

    Raises
    ------
    UnsupportedLanguageError
        If the language cannot be detected from the given path.
    """
    result = _detect_language(path)
    if result is None:
        raise UnsupportedLanguageError(f"Could not detect language for path: {path}")
    return result


def is_language_supported(language: str) -> bool:
    """Check whether a language name is supported by tree-sitter-language-pack.

    Attempts to obtain a parser for the given language. The library lazily
    downloads grammars on demand, so ``has_language`` from the language pack
    may return ``False`` even for languages that are fully supported.  We
    therefore try ``get_parser`` and treat any exception as "not supported".

    Parameters
    ----------
    language:
        The language name to check (e.g. ``"python"``, ``"rust"``).

    Returns
    -------
    bool
        ``True`` if a parser can be obtained for the language, ``False`` otherwise.
    """
    try:
        _ = get_parser(language)  # pyright: ignore[reportArgumentType]
    except Exception:  # noqa: BLE001
        return False
    return True
