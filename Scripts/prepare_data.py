import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler

# Load CSVs
falls = pd.read_csv('data/datasets/urfall-cam0-falls.csv', header=None)
adls  = pd.read_csv('data/datasets/urfall-cam0-adls.csv',  header=None)

# Add correct labels
falls['label'] = 1   # Fall = 1
adls['label']  = 0   # Non-fall = 0

# Combine
df = pd.concat([falls, adls], ignore_index=True)

# Keep only numeric feature columns (drop sequence name col)
feature_cols = df.select_dtypes(include=[np.number]).columns.tolist()
feature_cols.remove('label')  # don't scale the label

X = df[feature_cols].values
y = df['label'].values

# Scale
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Build sliding windows (30 frames, 15 frame overlap)
WINDOW = 30
STEP   = 15
sequences, labels = [], []

for i in range(0, len(X_scaled) - WINDOW, STEP):
    sequences.append(X_scaled[i:i+WINDOW])   # shape: (30, n_features)
    # Label = 1 if ANY frame in window is a fall
    labels.append(1 if y[i:i+WINDOW].sum() > 0 else 0)

sequences = np.array(sequences)  # shape: (N, 30, n_features)
labels    = np.array(labels)

np.save('data/processed/sequences.npy', sequences)
np.save('data/processed/labels.npy',    labels)
print(f"Sequences: {sequences.shape}, Labels: {labels.shape}")
print(f"Fall ratio: {labels.mean():.2%}")