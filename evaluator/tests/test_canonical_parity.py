import math

import pytest

from abe_eval.canonical import canonical_bytes, sha256_digest


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({"b": 2, "a": 1}, b'{"a":1,"b":2}'),
        (
            {"z": None, "a": [True, False, -7, 9007199254740991], "message": "caf\u00e9 \u2615"},
            '{"a":[true,false,-7,9007199254740991],"message":"caf\u00e9 \u2615","z":null}'.encode(),
        ),
        ({"": 1, "😀": 2}, '{"😀":2,"":1}'.encode()),
    ],
)
def test_canonical_bytes_match_shared_vectors(value, expected):
    assert canonical_bytes(value) == expected


def test_digest_matches_node_vector():
    assert sha256_digest(canonical_bytes({"b": 2, "a": 1})) == (
        "sha256:43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777"
    )


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, 1.5, 9007199254740992, -9007199254740992])
def test_rejects_non_shared_numbers(value):
    with pytest.raises(TypeError):
        canonical_bytes(value)
