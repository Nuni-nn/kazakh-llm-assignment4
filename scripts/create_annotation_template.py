from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parents[1]
RESP = ROOT / "data" / "responses_raw_template.csv"
OUT = ROOT / "data" / "human_annotations_template.csv"

FIELDS = [
    "run_id","Prompt_ID","model_name","annotator_id","word_count",
    "grammatical_errors","morphological_errors","lexical_errors",
    "orthographic_errors","script_mixing","code_switching","calque",
    "politeness_inconsistency","hallucinated_word","factual_error",
    "instruction_following_error","other_error_count","other_description",
    "primary_error_total","notes"
]

def main():
    with open(RESP, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    out_rows = []
    for r in rows:
        item = {k:"" for k in FIELDS}
        item["run_id"] = r["run_id"]
        item["Prompt_ID"] = r["Prompt_ID"]
        item["model_name"] = r["model_name"]
        item["annotator_id"] = ""
        out_rows.append(item)

    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out_rows)

    print(f"Created annotation template with {len(out_rows)} rows: {OUT}")

if __name__ == "__main__":
    main()
