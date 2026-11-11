from pathlib import Path

from scripts.check_test_taxonomy import find_taxonomy_violations


# Test taxonomy guard mirrors the standalone checker so CI fails if new tests are
# added to the old flat root layout.
def test_backend_test_taxonomy_has_no_flat_or_unknown_tests():
    tests_dir = Path(__file__).resolve().parents[1]

    assert find_taxonomy_violations(tests_dir) == []
