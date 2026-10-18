"""JSON schemas for structured outputs. Every field is required; 'empty' is "" / 0 / []."""

TYPES = ["empirical", "conceptual", "practice report", "method note", "review", "editorial", "other"]

_str = {"type": "string"}
_strs = {"type": "array", "items": {"type": "string"}}

FINDING = {
    "type": "object",
    "properties": {
        "id": _str,
        "k": {"type": "string", "enum": ["K1", "K2", "K3", "K4", "K5", "K6"]},
        "s": {"type": "integer", "enum": [1, 2, 3]},
        "c": {"type": "string", "enum": ["high", "medium", "low"]},
        "page_pdf": {"type": "integer"},
        "page_print": _str,
        "anchor": _str,
        "quote": _str,
        "problem": _str,
        "reported": _str,
        "expected": _str,
        "calc": _strs,
        "compare_page": {"type": "integer", "description": "0 if the finding is not a contradiction between two places"},
        "compare_anchor": _str,
        "compare_label": _str,
        "evidence": _str,
    },
    "required": ["id", "k", "s", "c", "page_pdf", "page_print", "anchor", "quote", "problem", "reported",
                 "expected", "calc", "compare_page", "compare_anchor", "compare_label", "evidence"],
    "additionalProperties": False,
}

REVIEW = {
    "type": "object",
    "properties": {
        "article": {
            "type": "object",
            "properties": {
                "title": _str, "authors": _str, "venue": _str, "year": _str,
                "type": {"type": "string", "enum": TYPES},
                "design": _str, "profile": _str, "verdict": _str,
                "checked_count": {"type": "integer"},
                "ok": _strs, "strengths": _strs, "limits": _strs,
            },
            "required": ["title", "authors", "venue", "year", "type", "design", "profile", "verdict",
                         "checked_count", "ok", "strengths", "limits"],
            "additionalProperties": False,
        },
        "findings": {"type": "array", "items": FINDING},
    },
    "required": ["article", "findings"],
    "additionalProperties": False,
}

VERIFY = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["confirmed", "partly", "refuted", "unclear"]},
        "corrected_severity": {"type": "integer", "enum": [0, 1, 2, 3], "description": "0 = unchanged"},
        "explanation": _str,
        "calc": _strs,
    },
    "required": ["verdict", "corrected_severity", "explanation", "calc"],
    "additionalProperties": False,
}

REFERENCES = {
    "type": "object",
    "properties": {
        "references": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": _str, "authors": _str, "year": _str, "doi": _str,
                    "type": {"type": "string", "enum": ["journal", "book", "chapter", "report", "thesis", "web", "other"]},
                },
                "required": ["title", "authors", "year", "doi", "type"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["references"],
    "additionalProperties": False,
}
