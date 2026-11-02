from pathlib import Path
import csv, json

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "Prompts500.csv"
CONFIG = ROOT / "config.json"
OUT = ROOT / "data" / "responses_raw_template.csv"

FIELDS = [
    "run_id","Prompt_ID","Subset","Task_Category","Domain","Difficulty",
    "model_key","model_name","model_version_exact","run_date_time",
    "prompt_text","raw_response","generation_status","error_message",
    "temperature","max_output_tokens","session_or_request_id"
]

def main():
    with open(DATA, "r", encoding="utf-8-sig", newline="") as f:
        prompts = list(csv.DictReader(f))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))

    rows = []
    n = 1
    for p in prompts:
        for m in config["models"]:
            rows.append({
                "run_id": f"RUN{n:04d}",
                "Prompt_ID": p["Prompt_ID"],
                "Subset": p["Subset"],
                "Task_Category": p["Task_Category"],
                "Domain": p["Domain"],
                "Difficulty": p["Difficulty"],
                "model_key": m["model_key"],
                "model_name": m["display_name"],
                "model_version_exact": "",
                "run_date_time": "",
                "prompt_text": p["Prompt_KK"],
                "raw_response": "",
                "generation_status": "NOT_RUN",
                "error_message": "",
                "temperature": "",
                "max_output_tokens": "",
                "session_or_request_id": ""
            })
            n += 1

    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    print(f"Created {len(rows)} rows: {OUT}")

if __name__ == "__main__":
    main()
