
import pytest

from src.mcp_service.utils import JsonConverter


@pytest.fixture
def converter():
    return JsonConverter()


def test_flatten_simple_dict(converter):
    data = {"a": 1, "b": {"c": 2}}
    flat = converter.flatten(data)
    assert flat["a"] == 1
    assert flat["b.c"] == 2


def test_flatten_with_list(converter):
    # Lists usually get JSON stringified if not exploded
    data = {"a": [1, 2]}
    flat = converter.flatten(data)
    assert flat["a"] == "[1, 2]"


def test_guess_records_list(converter):
    data = [{"a": 1}, {"a": 2}]
    records = converter.guess_records(data)
    assert len(records) == 2
    assert records[0]["a"] == 1


def test_guess_records_wrapped_dict(converter):
    # API often returns {"data": [...]}
    data = {"data": [{"id": 1}, {"id": 2}], "status": "ok"}
    records = converter.guess_records(data)
    assert len(records) == 2
    assert records[0]["id"] == 1


def test_explode_records(converter):
    # Explode a list inside a record into multiple rows
    data = [{"id": 1, "items": ["x", "y"]}]
    exploded = converter._explode_records(data, "items")

    assert len(exploded) == 2
    # First row
    assert exploded[0]["id"] == 1
    assert exploded[0]["items"]["value"] == "x"
    # Second row
    assert exploded[1]["id"] == 1
    assert exploded[1]["items"]["value"] == "y"


def test_json_to_vsc_text(converter):
    data = [{"name": "Alice", "role": "admin"}, {"name": "Bob", "role": "user"}]
    text, cols = converter.json_to_vsc_text(data, include_header=True)

    assert "name,role" in text or "role,name" in text
    assert "Alice,admin" in text
    assert "Bob,user" in text
