from pipeline.company_registry import (
    _merge_aliases,
    _record_to_registry_company,
    _strip_legal_suffix,
)


def test_strip_legal_suffix_removes_common_suffixes():
    assert _strip_legal_suffix("Example S.A.") == "Example"
    assert _strip_legal_suffix("Example sp. z o.o.") == "Example"
    assert _strip_legal_suffix("Example") is None


def test_record_to_registry_company_extracts_name_and_tags():
    record = {
        "id": "2594008SQ7L4NNO6R013",
        "attributes": {
            "entity": {
                "legalName": {"name": "Hype S.A."},
                "otherNames": [{"name": "Hype"}],
                "transliteratedOtherNames": [{"name": "HYPE JOINT STOCK"}],
                "registeredAs": "0001195899",
            }
        },
    }

    parsed = _record_to_registry_company(record)

    assert parsed is not None
    assert parsed.name == "Hype S.A."
    assert parsed.lei_tag == "LEI:2594008SQ7L4NNO6R013"
    assert "Hype" in parsed.aliases
    assert "HYPE JOINT STOCK" in parsed.aliases
    assert "REG:0001195899" in parsed.aliases
    assert "LEI:2594008SQ7L4NNO6R013" in parsed.aliases


def test_merge_aliases_keeps_first_case_insensitively():
    merged = _merge_aliases(["Alpha", "LEI:abc"], ["alpha", "lei:ABC", "Beta"])
    assert merged == ["Alpha", "LEI:abc", "Beta"]
