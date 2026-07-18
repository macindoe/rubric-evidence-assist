import argparse
import json
from pathlib import Path

from src.marking import mark_essay


def main():
    parser = argparse.ArgumentParser(
        description="Slice 0: rubric-evidence extraction proof of concept."
    )
    parser.add_argument("--text", required=True, type=Path, help="Path to a plain-text essay extract.")
    parser.add_argument("--rubric", required=True, type=Path, help="Path to the rubric JSON.")
    parser.add_argument("--out", type=Path, default=None, help="Optional path to save the JSON result.")
    args = parser.parse_args()

    essay_text = args.text.read_text(encoding="utf-8")
    rubric = json.loads(args.rubric.read_text(encoding="utf-8"))

    result = mark_essay(essay_text, rubric)

    print(json.dumps(result, indent=2))

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\nSaved to {args.out}")


if __name__ == "__main__":
    main()
