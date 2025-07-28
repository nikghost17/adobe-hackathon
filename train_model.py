import pandas as pd
import os
import joblib
import re
import numpy as np
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier
from sklearn.metrics import classification_report
from sklearn.preprocessing import OneHotEncoder
import matplotlib.pyplot as plt

# --- PATHS CORRECTED FOR LOCAL DEVELOPMENT ---
# This script runs on your machine, not in Docker.
# Use relative paths from your project root.

# 📂 Load Data
csv_path = "headings_dataset_4.csv"  # CORRECTED PATH
if not os.path.exists(csv_path):
    raise FileNotFoundError(f"❌ CSV file not found at: {csv_path}. Make sure you run this script from the project root directory.")

df = pd.read_csv(csv_path)
print(f"✅ Loaded {len(df)} rows from CSV.")

# 🪪 Filter and map labels
label_mapping = {f"H{i}": i-1 for i in range(1, 6)}
df = df[df['label'].isin(label_mapping.keys())].copy() # Use .copy() to avoid SettingWithCopyWarning
print(f"✅ Rows after label filtering: {len(df)}")
df['label'] = df['label'].map(label_mapping)

# 🔧 Normalize boolean features
bool_cols = ['is_bold', 'is_numbered', 'has_colon']
for col in bool_cols:
    if col in df.columns:
        df[col] = df[col].astype(str).str.strip().str.lower().map({'true': 1, 'false': 0})
    else:
        raise KeyError(f"❌ Column '{col}' not found in CSV!")

# 🔢 Convert numeric features
num_cols = ['page', 'font_size', 'indentation', 'line_length']
for col in num_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    else:
        raise KeyError(f"❌ Column '{col}' not found in CSV!")

# 🧹 Drop rows with missing values
print(f"🧼 Rows before dropna: {len(df)}")
df.dropna(inplace=True)
print(f"🧼 Rows after dropna: {len(df)}")

# --- Feature Engineering ---
def count_digits(text):
    return sum(c.isdigit() for c in text)

def count_uppercase(text):
    return sum(c.isupper() for c in text)

def has_special_char(text):
    return int(bool(re.search(r'[^a-zA-Z0-9\s]', text)))

print("🛠️ Extracting text features...")
df['num_digits'] = df['heading_text'].apply(lambda x: count_digits(str(x)))
df['num_uppercase'] = df['heading_text'].apply(lambda x: count_uppercase(str(x)))
df['has_special_char'] = df['heading_text'].apply(lambda x: has_special_char(str(x)))

# One-Hot Encode categorical features
cat_cols = [col for col in ['font_name', 'alignment'] if col in df.columns]
ohe = None
cat_feature_names = []

if cat_cols:
    print(f"🛠️ Encoding categorical features: {cat_cols}")
    ohe = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
    cat_features = ohe.fit_transform(df[cat_cols])
    cat_feature_names = ohe.get_feature_names_out(cat_cols)
    df_ohe = pd.DataFrame(cat_features, columns=cat_feature_names, index=df.index)
    df = pd.concat([df, df_ohe], axis=1)
else:
    print("⚠️ No categorical columns to encode.")

# Final list of features
features_numeric_bool = ['page', 'font_size', 'is_bold', 'indentation', 'is_numbered', 'has_colon', 'line_length', 'num_digits', 'num_uppercase', 'has_special_char']
features_final = features_numeric_bool + (cat_feature_names.tolist() if cat_feature_names else [])

print(f"🧩 Final features used for training: {features_final}")

missing_features = [f for f in features_final if f not in df.columns]
if missing_features:
    raise ValueError(f"🚨 Missing features in DataFrame after encoding: {missing_features}")

X = df[features_final]
y = df['label']

# 🧪 Train/Test split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
print(f"📊 Split: {len(X_train)} train / {len(X_test)} test")

# 🤖 Initialize and train model
model = XGBClassifier(use_label_encoder=False, eval_metric='mlogloss', random_state=42)
model.fit(X_train, y_train)
print("✅ Model training complete.")

# 🧠 Evaluate
y_pred = model.predict(X_test)
print("📈 Classification report:\n", classification_report(y_test, y_pred))

# 💾 --- SAVING MODELS WITH CORRECTED PATHS ---
output_model_dir = "models"
os.makedirs(output_model_dir, exist_ok=True) # BEST PRACTICE: Create dir if it doesn't exist

model_path = os.path.join(output_model_dir, "xgb_heading_classifier_with_text.pkl")
joblib.dump(model, model_path)
print(f"✅ Model saved to {model_path}")

if ohe:
    encoder_path = os.path.join(output_model_dir, "onehot_encoder.pkl")
    joblib.dump(ohe, encoder_path)
    print(f"✅ OneHotEncoder saved to {encoder_path}")

# Note: The plot will show up on your screen. You can close it to finish the script.
print("📊 Displaying feature importance plot...")
importances = model.feature_importances_
indices = np.argsort(importances)[::-1]
plt.figure(figsize=(12, 8))
plt.title("Feature Importance")
plt.bar(range(len(importances)), importances[indices], align='center')
plt.xticks(range(len(importances)), [features_final[i] for i in indices], rotation=90)
plt.tight_layout()
plt.show()

print("🏁 Training script finished successfully.")