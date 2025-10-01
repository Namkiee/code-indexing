
import csv, argparse, math
from collections import defaultdict

def dcg(scores): return sum(((2**s -1)/math.log2(i+2) for i,s in enumerate(scores)))
def ndcg(rel): ideal = sorted(rel, reverse=True); denom = dcg(ideal); return (dcg(rel)/denom) if denom>0 else 0.0
def average_precision(labels):
    num_rel = sum(labels); 
    if num_rel==0: return 0.0
    hit=0; precs=[]; 
    for i,y in enumerate(labels, start=1):
        if y==1: hit+=1; precs.append(hit/i)
    return sum(precs)/num_rel

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("csv_file"); ap.add_argument("--score-col", default="fused")
    args = ap.parse_args()
    rows = defaultdict(list)
    with open(args.csv_file, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r: rows[row["search_id"]].append((float(row[args.score_col]), int(row["label"])))
    Ks=[3,5,10]; nd={k:[] for k in Ks}; mp={k:[] for k in Ks}
    for sid, arr in rows.items():
        arr.sort(key=lambda x:x[0], reverse=True)
        for k in Ks:
            top = arr[:k]; nd[k].append(ndcg([l for _,l in top])); mp[k].append(average_precision([l for _,l in top]))
    for k in Ks: print(f"NDCG@{k}: {sum(nd[k])/len(nd[k]) if nd[k] else 0:.4f}  MAP@{k}: {sum(mp[k])/len(mp[k]) if mp[k] else 0:.4f}")
if __name__=="__main__": main()
