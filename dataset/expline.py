import pandas as pd
import shap
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
import matplotlib
matplotlib.use("Agg")

X = pd.read_csv("data/features.csv")
y = pd.read_csv("data/labels.csv")["label"]
y_bin = (y == "ai_spam").astype(int)

X_train, X_test, y_train, y_test = train_test_split(
    X, y_bin, test_size=0.3, random_state=42, stratify=y_bin
)

clf = LogisticRegression(max_iter=1000, class_weight="balanced")
clf.fit(X_train, y_train)

explainer = shap.LinearExplainer(clf, X_train)
shap_values = explainer.shap_values(X_test)

# Глобальная важность
shap.summary_plot(shap_values, X_test, feature_names=X.columns, show=False)
import matplotlib.pyplot as plt
plt.savefig("data/shap_summary.png", bbox_inches="tight")
plt.close()
global_importance = np.abs(shap_values).mean(axis=0)
print("\n--- Глобальная важность (mean |SHAP|) ---")
for name, val in sorted(zip(X.columns, global_importance), key=lambda x: -x[1]):
    print(f"  {name:20s} {val:.4f}")
# Для одного примера
print("--- Пример объяснения ---")
i = 0
row = X_test.iloc[i]
print(f"Прогноз: {'AI-spam' if clf.predict([row])[0] else 'Not AI'}")
print("Вклад признаков:")
for name, val in sorted(zip(X.columns, shap_values[i]), key=lambda x: -abs(x[1])):
    print(f"  {name:20s} {val:+.3f}")