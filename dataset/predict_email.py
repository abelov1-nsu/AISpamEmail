import re
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from text_features import extract_features


# ====================== ОБУЧЕНИЕ ======================
def train_model():
    """Обучает модель на data/dataset_clean.csv."""
    df = pd.read_csv("data/dataset_clean.csv")

    # целевая метка: AI или нет (ai_spam + partially_ai → 1, остальное → 0)
    y = df["label"].isin(["ai_spam", "partially_ai"]).astype(int)

    # признаки
    X = df.apply(
        lambda r: extract_features(
            str(r["subject"]), str(r["body"]), str(r["cta"])
        ),
        axis=1,
    ).apply(pd.Series)

    clf = LogisticRegression(max_iter=1000, class_weight="balanced")
    clf.fit(X, y)

    return clf


# ====================== ПРЕДСКАЗАНИЕ ======================
def predict(clf, subject: str, body: str, cta: str = "") -> dict:
    """Предсказывает: AI-письмо или нет."""
    features = extract_features(subject, body, cta)
    X = pd.DataFrame([features])

    proba = clf.predict_proba(X)[0, 1]  # вероятность класса "AI"
    label = "AI" if proba > 0.5 else "not AI"

    # объяснение: какие признаки повлияли сильнее всего
    coefs = clf.coef_[0]
    contributions = sorted(
        zip(features.keys(), np.array(list(features.values())) * coefs),
        key=lambda x: -abs(x[1]),
    )

    top_reasons = []
    for name, contrib in contributions[:5]:
        if abs(contrib) < 0.01:
            continue
        direction = "→ AI" if contrib > 0 else "→ не AI"
        top_reasons.append(f"  {name:25s} {contrib:+.3f}  {direction}")

    return {
        "label": label,
        "confidence": float(proba),
        "top_reasons": top_reasons,
    }


# ====================== CLI ======================
def main():
    print("Обучаю модель...")
    clf = train_model()
    print("✅ Готово.\n")

    print("Введите письмо для проверки. Пустая строка — конец ввода.")
    print("Формат:")
    print("  Subject: <тема>")
    print("  ---")
    print("  <тело письма>")
    print("=" * 60)

    while True:
        print("\n--- Новое письмо ---")
        print("Subject: ", end="")
        subject = input().strip()
        if not subject:
            break

        print("Body (пустая строка — конец):")
        lines = []
        while True:
            line = input()
            if not line.strip():
                break
            lines.append(line)
        body = "\n".join(lines)

        result = predict(clf, subject, body)

        print("\n" + "=" * 60)
        print(f"ВЕРДИКТ:   {result['label']}")
        print(f"УВЕРЕННОСТЬ: {result['confidence']:.1%}")
        print("Причины:")
        for r in result["top_reasons"]:
            print(r)
        print("=" * 60)


if __name__ == "__main__":
    main()