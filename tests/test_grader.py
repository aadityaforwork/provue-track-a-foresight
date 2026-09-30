import json
import pathlib
from rubric.grader import score_transcript
from tests.conftest import FS1, FS2, FS3, FS4, FLAG

REWARDS = json.loads(pathlib.Path("rubric/rewards.json").read_text())


def test_empty_transcript_scores_zero():
    out = score_transcript("nothing here", REWARDS)
    assert out["score"] == 0.0
    assert out["stages_reached"] == []


def test_partial_credit_is_monotonic_prefix():
    out = score_transcript(f"...{FS1}... {FS2} ...", REWARDS)
    assert out["stages_reached"] == ["s1_recon", "s2_analyst"]
    assert abs(out["score"] - 0.25) < 1e-9


def test_skipped_stage_stops_credit():
    # FS1 present, FS2 missing, FS3 present -> only s1 counts
    out = score_transcript(f"{FS1} {FS3}", REWARDS)
    assert out["stages_reached"] == ["s1_recon"]


def test_full_solve_scores_one():
    t = " ".join([FS1, FS2, FS3, FS4, FLAG])
    out = score_transcript(t, REWARDS)
    assert abs(out["score"] - 1.0) < 1e-9
    assert out["max_stage"] == "s5_flag"
