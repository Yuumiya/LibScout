from __future__ import annotations

from .chunking import extract_cst_chunks
from .detector import detect_language, is_language_supported
from .models import CSTChunk, ParseError, ParseResult, UnsupportedLanguageError
from .parser import parse_code, parse_file

__all__: list[str] = [
    "CSTChunk",
    "ParseError",
    "ParseResult",
    "UnsupportedLanguageError",
    "__version__",
    "extract_cst_chunks",
    "detect_language",
    "is_language_supported",
    "parse_code",
    "parse_file",
]

__version__ = "0.1.0"
