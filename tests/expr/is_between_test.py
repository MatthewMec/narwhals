from __future__ import annotations

from typing import Any

import pytest

import narwhals.stable.v1 as nw
from tests.utils import compare_dicts

data = {
    "a": [1, 4, 2, 5],
}


@pytest.mark.parametrize(
    ("closed", "expected"),
    [
        ("left", [True, True, True, False]),
        ("right", [False, True, True, True]),
        ("both", [True, True, True, True]),
        ("none", [False, True, True, False]),
    ],
)
def test_is_between(constructor: Any, closed: str, expected: list[bool]) -> None:
    df = nw.from_native(constructor(data), eager_only=True)
    result = df.select(nw.col("a").is_between(1, 5, closed=closed))
    expected_dict = {"a": expected}
    compare_dicts(result, expected_dict)
    result = df.with_columns(a=df["a"].is_between(1, 5, closed=closed))
    compare_dicts(result, expected_dict)
