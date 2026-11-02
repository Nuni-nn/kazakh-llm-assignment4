from pathlib import Path
import csv, hashlib, sys
from collections import Counter

DATA = Path(__file__).resolve().parents[1] / "data" / "Prompts500.csv"

REQUIRED = [
    "Prompt_ID","Subset","Task_Category","Domain","Domain_KK","Difficulty",
    "Prompt_KK","Target_Length","Key_Terms","Linguistic_Stress",
    "Source_EN","Reference_KK","Reference_Source","Protocol_Note"
]

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    if not DATA.exists():
        print(f"ERROR: Dataset not found: {DATA}")
        sys.exit(1)

    with open(DATA, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    errors = []
    missing_cols = [c for c in REQUIRED if c not in (rows[0].keys() if rows else [])]
    if missing_cols:
        errors.append(f"Missing columns: {missing_cols}")

    if len(rows) != 500:
        errors.append(f"Expected 500 rows, found {len(rows)}")

    ids = [r.get("Prompt_ID","").strip() for r in rows]
    if len(ids) != len(set(ids)):
        errors.append("Duplicate Prompt_ID values found")

    texts = [r.get("Prompt_KK","").strip() for r in rows]
    if len(texts) != len(set(texts)):
        errors.append("Duplicate Prompt_KK values found")

    subset = Counter(r.get("Subset","") for r in rows)
    difficulty = Counter(r.get("Difficulty","") for r in rows)

    if subset.get("Open-ended",0) != 400:
        errors.append(f"Expected 400 Open-ended, found {subset.get('Open-ended',0)}")
    if subset.get("Reference-based",0) != 100:
        errors.append(f"Expected 100 Reference-based, found {subset.get('Reference-based',0)}")

    for d in ["Basic","Intermediate","Advanced","Expert"]:
        if difficulty.get(d,0) != 125:
            errors.append(f"Expected 125 {d}, found {difficulty.get(d,0)}")

    # Reference subset must have source and reference text
    for i, r in enumerate(rows, start=2):
        if r.get("Subset") == "Reference-based":
            if not r.get("Source_EN","").strip():
                errors.append(f"Row {i}: missing Source_EN for reference-based prompt")
            if not r.get("Reference_KK","").strip():
                errors.append(f"Row {i}: missing Reference_KK for reference-based prompt")

    print("=== DATASET VALIDATION ===")
    print("Rows:", len(rows))
    print("Subset:", dict(subset))
    print("Difficulty:", dict(difficulty))
    print("SHA-256:", sha256(DATA))

    if errors:
        print("\nFAILED:")
        for e in errors:
            print("-", e)
        sys.exit(1)

    print("\nPASS: Dataset is internally consistent.")

if __name__ == "__main__":
    main()
