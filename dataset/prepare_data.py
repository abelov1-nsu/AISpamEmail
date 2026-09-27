import pandas as pd
import os

TARGET_COLS = ["id", "subject", "body", "cta", "label"]
os.makedirs("data", exist_ok=True)


def finalize(df, id_prefix, label):
    if "subject" not in df.columns:
        df["subject"] = ""
    if "body" not in df.columns:
        df["body"] = ""
    if "cta" not in df.columns:
        df["cta"] = ""

    # Всегда перегенерируем id — чтобы не было дублей при concat
    df = df.reset_index(drop=True)
    df["id"] = [f"{id_prefix}_{str(i).zfill(4)}" for i in range(len(df))]

    df["label"] = label
    df = df[TARGET_COLS].copy()

    for col in ["subject", "body", "cta"]:
        df[col] = df[col].fillna("").astype(str)

    return df

# ---------- 1. SpamAssassin (human_spam) ----------
df_spam = pd.read_csv("data/dataset_spamassassin.csv")
df_spam = finalize(df_spam, id_prefix="spam", label="human_spam")
print(f"SpamAssassin: {len(df_spam)}")


# ---------- 2. AI-spam ----------
ai_files = [
    "data/dataset_ai_spam.csv",
    "data/dataset_ai_spam_2.csv",
]

ai_frames = []
for f in ai_files:
    if os.path.exists(f):
        tmp = pd.read_csv(
            f,
            engine="python",
            on_bad_lines="skip",
        )
        # добавляем ссылку в body как сигнал
        if "link" in tmp.columns:
            tmp["body"] = (
                tmp["body"].astype(str)
                + "\n\nLink: "
                + tmp["link"].fillna("").astype(str)
            )
        ai_frames.append(tmp)
        print(f"  + {f}: {len(tmp)}")
    else:
        print(f"  ⚠️ Нет файла: {f}")

df_ai = pd.concat(ai_frames, ignore_index=True)
df_ai = finalize(df_ai, id_prefix="ai", label="ai_spam")
print(f"AI-spam всего: {len(df_ai)}")
# ---------- 3. Enron (только ham → legit) ----------
df_enron = pd.read_csv("data/enron_spam_data.csv")
print(f"Enron всего: {len(df_enron)}")
df_enron = df_enron[df_enron["Spam/Ham"] == "ham"].copy()
df_enron = df_enron.rename(columns={
    "Subject": "subject",
    "Message": "body",
})
df_enron = finalize(df_enron, id_prefix="enron", label="legit")
print(f"Enron ham: {len(df_enron)}")


# ---------- 4. Слияние ----------
df_final = pd.concat([df_spam, df_ai, df_enron], ignore_index=True)

# убираем пустые письма
df_final = df_final[df_final["body"].str.len() > 20].reset_index(drop=True)

# убираем дубликаты по body
before = len(df_final)
df_final = df_final.drop_duplicates(subset=["body"]).reset_index(drop=True)
print(f"Убрано дубликатов: {before - len(df_final)}")

# ---------- 5. Балансировка ----------
# ---------- 5. Балансировка ----------
MIN_PER_CLASS = 50

balanced = []
for label, group in df_final.groupby("label"):
    n = min(len(group), MIN_PER_CLASS)
    balanced.append(group.sample(n, random_state=42))

df_final = pd.concat(balanced, ignore_index=True)

# ---------- 6. Сохранение ----------
df_final.to_csv("data/dataset.csv", index=False, encoding="utf-8")

print("\n" + "=" * 50)
print(f"✅ Итого писем: {len(df_final)}")
print(df_final["label"].value_counts())
print("\nСредняя длина body по классам:")
print(df_final.groupby("label")["body"].apply(lambda x: int(x.str.len().mean())))
