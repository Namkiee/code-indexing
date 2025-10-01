
import csv, argparse
from collections import defaultdict
from evaluate_ranker import ndcg, average_precision

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_file")
    ap.add_argument("--alphas", default="0.0,0.2,0.4,0.6,0.8,1.0")
    ap.add_argument("--betas", default="0.0,0.2,0.4,0.6,0.8,1.0")
    args = ap.parse_args()
    rows = defaultdict(list)
    with open(args.csv_file, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r: rows[row["search_id"]].append((float(row["vnorm"]), float(row["bnorm"]), int(row["label"])))
    alphas=[float(x) for x in args.alphas.split(",")]; betas=[float(x) for x in args.betas.split(",")]
    best=None
    for a in alphas:
        for b in betas:
            nd, mp = [], []
            for sid, arr in rows.items():
                scored = [(a*v + b*bm, l) for v,bm,l in arr]
                scored.sort(key=lambda x:x[0], reverse=True)
                top = scored[:10]; nd.append(ndcg([l for _,l in top])); mp.append(average_precision([l for _,l in top]))
            score = (sum(nd)/len(nd) if nd else 0) + (sum(mp)/len(mp) if mp else 0)
            if best is None or score>best[0]: best=(score,a,b)
    if best: print(f"BEST sum(NDCG@10 + MAP@10) = {best[0]:.4f} at alpha={best[1]}, beta={best[2]}")
    else: print("No data.")
if __name__=="__main__": main()
