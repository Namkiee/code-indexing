
import sys, csv, joblib
from sklearn.linear_model import LogisticRegression
import numpy as np
def main():
    if len(sys.argv) < 3:
        print("Usage: train_ranker.py data.csv model.joblib"); raise SystemExit(1)
    data_csv, out = sys.argv[1], sys.argv[2]
    X, y = [], []
    with open(data_csv, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r: X.append([float(row["fused"]), float(row["vnorm"]), float(row["bnorm"]), float(row["span"]), float(row["depth"])]); y.append(int(row["label"]))
    clf = LogisticRegression(max_iter=1000); clf.fit(np.array(X), np.array(y)); joblib.dump(clf, out); print("Saved:", out)
if __name__ == "__main__": main()
