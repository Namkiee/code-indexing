
import csv, argparse
from app.utils.jsonl import iter_jsonl

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--search-log", default="server/data/search_log.jsonl")
    ap.add_argument("--feedback-log", default="server/data/feedback_log.jsonl")
    ap.add_argument("--out", default="server/data/training.csv")
    args = ap.parse_args()

    feedback = {}
    for row in iter_jsonl(args.feedback_log):
        sid = row.get("search_id"); cid = row.get("clicked_chunk_id"); grade = int(row.get("grade",1))
        if not sid or not cid: continue
        feedback.setdefault(sid, {})[cid] = 1 if grade > 0 else 0

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["search_id","chunk_id","fused","vnorm","bnorm","span","depth","label"])
        for row in iter_jsonl(args.search_log):
            sid = row.get("search_id"); cands = row.get("candidates", [])
            labels = feedback.get(sid, {})
            for c in cands:
                cid = c["chunk_id"]
                label = int(labels.get(cid, 0))
                w.writerow([sid, cid, c["fused"], c["vnorm"], c["bnorm"], c["span"], c["depth"], label])
    print("Saved:", args.out)

if __name__ == "__main__":
    main()
