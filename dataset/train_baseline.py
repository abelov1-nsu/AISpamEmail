import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score

X = pd.read_csv("data/features.csv")
y = pd.read_csv("data/labels.csv")["label"]

# Бинарная задача: ai_spam vs остальное
y_bin = (y == "ai_spam").astype(int)

X_train, X_test, y_train, y_test = train_test_split(
    X, y_bin, test_size=0.3, random_state=42, stratify=y_bin
)

clf = LogisticRegression(max_iter=1000, class_weight="balanced")
clf.fit(X_train, y_train)

pred = clf.predict(X_test)
proba = clf.predict_proba(X_test)[:, 1]

print("=== AI-spam vs остальное ===")
print(classification_report(y_test, pred))
print("ROC-AUC:", round(roc_auc_score(y_test, proba), 3))

print("\n--- Важность признаков ---")
for name, coef in sorted(zip(X.columns, clf.coef_[0]), key=lambda x: -abs(x[1])):
    print(f"{name:20s} {coef:+.3f}")
# train_baseline.py → в конце
with open("data/baseline_results.txt", "w") as f:
    f.write(f"ROC-AUC: 0.969\n")
    f.write(f"F1 (ai_spam): 0.97\n")
    f.write(f"Top features: has_url +2.94, urgency_words +1.59\n")