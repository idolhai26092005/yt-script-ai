import os
import json
import pytest
from app.services.production.validation.legacy import validate_scene, validate_script, normalize_scene, normalize_script

SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "snapshots", "series-2")
BASELINE_PATH = os.path.join(SNAPSHOT_DIR, "baseline_validation.json")

if not os.path.exists(SNAPSHOT_DIR) or not os.path.exists(BASELINE_PATH):
    pytestmark = pytest.mark.skip(reason="Regression snapshot files are missing (deleted or untracked)")

def load_baseline():
    with open(BASELINE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

@pytest.mark.parametrize("filename", ["ex1.json", "ex2.json", "ex3.json"])
def test_snapshot_validation_regression(filename):
    # Load expectations
    baseline = load_baseline()
    expected = baseline.get(filename)
    assert expected is not None, f"No baseline expectations found for {filename}"

    # Load legacy script snapshot
    snapshot_path = os.path.join(SNAPSHOT_DIR, filename)
    with open(snapshot_path, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    # 1. Run script level validation
    script_errors = validate_script(normalize_script(script_data))

    # 2. Run scene level validation
    scene_errors = []
    scenes = script_data.get("scenes", [])
    anchor = {"continuity_prompt_en": script_data.get("continuity_board", {}).get("continuity_prompt_en", "")}
    for scene in scenes:
        s_num = scene.get("scene_number", "?")
        errors = validate_scene(normalize_scene(scene), anchor)
        for err in errors:
            scene_errors.append(f"Scene {s_num}: {err}")


    # 3. Assert exact matches against baseline expectations
    assert script_errors == expected.get("script_validation_errors", []), \
        f"Mismatched script validation errors for {filename}"
    assert scene_errors == expected.get("scene_validation_errors", []), \
        f"Mismatched scene validation errors for {filename}"
    
    total_errors = len(script_errors) + len(scene_errors)
    assert total_errors == expected.get("total_errors", 0), \
        f"Mismatched total validation errors count for {filename}"
