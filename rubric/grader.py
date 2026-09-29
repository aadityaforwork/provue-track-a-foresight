import json
import re
import sys


def score_transcript(transcript: str, rewards: list) -> dict:
    score = 0.0
    reached = []
    for stage in rewards:
        if re.search(stage["check"], transcript):
            score += stage["score"]
            reached.append(stage["id"])
        else:
            break  # monotonic: stop at first unmet stage
    return {
        "score": round(score, 6),
        "max_stage": reached[-1] if reached else None,
        "stages_reached": reached,
    }


if __name__ == "__main__":
    rewards = json.load(open("rubric/rewards.json"))
    transcript = sys.stdin.read()
    print(json.dumps(score_transcript(transcript, rewards)))
