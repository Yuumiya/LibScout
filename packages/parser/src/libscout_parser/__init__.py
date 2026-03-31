from __future__ import annotations

from .detector import detect_language, is_language_supported
from .models import ParseError, ParseResult, UnsupportedLanguageError
from .parser import parse_code, parse_file

__all__: list[str] = [
    "ParseError",
    "ParseResult",
    "UnsupportedLanguageError",
    "__version__",
    "detect_language",
    "is_language_supported",
    "parse_code",
    "parse_file",
]

__version__ = "0.1.0"
