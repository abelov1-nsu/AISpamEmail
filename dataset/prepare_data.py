import os
import json
import pandas as pd

TARGET_COLS = ["id", "subject", "body", "cta", "label"]
os.makedirs("data", exist_ok=True)


# ====================== НОРМАЛИЗАЦИЯ ======================
def finalize(df, id_prefix, label):
    """Приводит любой df к целевому формату."""
    if "subject" not in df.columns:
        df["subject"] = ""
    if "body" not in df.columns:
        df["body"] = ""
    if "cta" not in df.columns:
        df["cta"] = ""

    if "id" not in df.columns:
        df = df.reset_index(drop=True)
        df["id"] = [f"{id_prefix}_{str(i).zfill(4)}" for i in range(len(df))]

    df["label"] = label
    df = df[TARGET_COLS].copy()

    for col in ["subject", "body", "cta"]:
        df[col] = df[col].fillna("").astype(str)

    return df


# ====================== 1. SPAMASSASSIN ======================
df_spam = pd.read_csv("data/dataset_spamassassin.csv")
df_spam = finalize(df_spam, id_prefix="spam", label="human_spam")
print(f"SpamAssassin: {len(df_spam)}")


# ====================== 2. AI-SPAM ======================
ai_files = [
    "data/dataset_ai_spam.csv",
    "data/dataset_ai_spam_2.csv",
]

ai_frames = []
for f in ai_files:
    if not os.path.exists(f):
        print(f"  ⚠️ Нет файла: {f}")
        continue

    try:
        tmp = pd.read_csv(f, engine="python", on_bad_lines="skip")
    except pd.errors.EmptyDataError:
        print(f"  ⚠️ Пустой файл: {f}")
        continue
    except Exception as e:
        print(f"  ⚠️ Ошибка чтения {f}: {e}")
        continue

    if len(tmp) == 0:
        print(f"  ⚠️ 0 строк: {f}")
        continue

    # добавляем link в body как сигнал
    if "link" in tmp.columns:
        tmp["body"] = (
            tmp["body"].astype(str)
            + "\n\nLink: "
            + tmp["link"].fillna("").astype(str)
        )

    # убираем старые id, чтобы finalize создал новые (без дублей)
    tmp = tmp.drop(columns=["id"], errors="ignore")

    ai_frames.append(tmp)
    print(f"  + {f}: {len(tmp)}")

if ai_frames:
    df_ai = pd.concat(ai_frames, ignore_index=True)
    df_ai = finalize(df_ai, id_prefix="ai", label="ai_spam")
    print(f"AI-spam всего: {len(df_ai)}")
else:
    df_ai = pd.DataFrame(columns=TARGET_COLS)
    print("AI-spam: 0 (нет файлов)")


# ====================== 3. PARTIALLY AI ======================
partial_files = [
    "data/dataset_ai_spam_partial.json",
]

partial_frames = []
for f in partial_files:
    if not os.path.exists(f):
        print(f"  ⚠️ Нет файла: {f}")
        continue

    try:
        tmp = pd.read_json(f)
    except Exception as e:
        print(f"  ⚠️ Ошибка чтения {f}: {e}")
        continue

    if len(tmp) == 0:
        print(f"  ⚠️ 0 строк: {f}")
        continue

    if "link" in tmp.columns:
        tmp["body"] = (
            tmp["body"].astype(str)
            + "\n\nLink: "
            + tmp["link"].fillna("").astype(str)
        )

    tmp = tmp.drop(columns=["id"], errors="ignore")
    partial_frames.append(tmp)
    print(f"  + {f}: {len(tmp)}")

if partial_frames:
    df_partial = pd.concat(partial_frames, ignore_index=True)
    df_partial = finalize(df_partial, id_prefix="partial", label="partially_ai")
    print(f"Partially AI всего: {len(df_partial)}")
else:
    df_partial = pd.DataFrame(columns=TARGET_COLS)
    print("Partially AI: 0 (нет файлов)")


# ====================== 4. ENRON (legit) ======================
df_enron = pd.read_csv("data/enron_spam_data.csv")
print(f"Enron всего: {len(df_enron)}")

df_enron = df_enron[df_enron["Spam/Ham"] == "ham"].copy()
df_enron = df_enron.rename(columns={"Subject": "subject", "Message": "body"})
df_enron = finalize(df_enron, id_prefix="enron", label="legit")
print(f"Enron ham: {len(df_enron)}")


# ====================== 5. СЛИЯНИЕ ======================
df_final = pd.concat(
    [df_spam, df_ai, df_partial, df_enron],
    ignore_index=True,
)

# убираем пустые и слишком короткие
df_final = df_final[df_final["body"].str.len() > 20].reset_index(drop=True)

# обрезаем длинные body
df_final["body"] = df_final["body"].str.slice(0, 2000)

# убираем дубликаты
before = len(df_final)
df_final = df_final.drop_duplicates(subset=["body"]).reset_index(drop=True)
print(f"Убрано дубликатов: {before - len(df_final)}")


# ====================== 6. БАЛАНСИРОВКА ======================
MIN_PER_CLASS = 50

balanced = []
for label, group in df_final.groupby("label"):
    n = min(len(group), MIN_PER_CLASS)
    balanced.append(group.sample(n, random_state=42))

df_final = pd.concat(balanced, ignore_index=True)


# ====================== 7. СОХРАНЕНИЕ ======================
df_final.to_csv("data/dataset.csv", index=False, encoding="utf-8")

print("\n" + "=" * 50)
print(f"✅ Итого писем: {len(df_final)}")
print(df_final["label"].value_counts())
print("\nСредняя длина body по классам:")
print(df_final.groupby("label")["body"].apply(lambda x: int(x.str.len().mean())))
