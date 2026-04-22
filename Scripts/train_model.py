import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import numpy as np
import pandas as pd
import os

# ============================================================
# 1. NMMCU Activation Function
# ============================================================
class NMMCU(nn.Module):
    """Non-Monotonic Mish Cubic Unit"""
    def forward(self, x):
        mish = x * torch.tanh(torch.log(1 + torch.exp(x)))
        return mish - (x ** 3)


# ============================================================
# 2. Model Architecture (CNN + LSTM Hybrid)
# ============================================================
class FallHybridModel(nn.Module):
    def __init__(self, input_dim):
        super(FallHybridModel, self).__init__()

        # Temporal CNN — learns short motion patterns (e.g., sudden jerk)
        self.conv = nn.Conv1d(input_dim, 64, kernel_size=3, padding=1)
        self.nmmcu = NMMCU()

        # Dropout for regularization
        self.dropout = nn.Dropout(p=0.3)

        # LSTM — learns the full fall sequence over time
        self.lstm = nn.LSTM(64, 128, num_layers=2, batch_first=True, dropout=0.3)

        # Output layer — single sigmoid output (fall probability)
        self.fc = nn.Linear(128, 1)

    def forward(self, x):
        # x shape: (batch, seq_len, features)
        x = x.transpose(1, 2)              # → (batch, features, seq_len) for Conv1d
        x = self.nmmcu(self.conv(x))       # → (batch, 64, seq_len)
        x = self.dropout(x)
        x = x.transpose(1, 2)             # → (batch, seq_len, 64) for LSTM
        _, (hn, _) = self.lstm(x)         # hn shape: (num_layers, batch, 128)
        out = self.fc(hn[-1])             # Take last layer hidden state
        return torch.sigmoid(out)         # → (batch, 1)


# ============================================================
# 3. Build Sliding Window Sequences from CSVs
# ============================================================
def build_sequences(window_size=30, step=15):
    """
    Reads the raw CSVs, assigns correct labels,
    scales features, and builds sliding window sequences.

    Returns:
        sequences : np.array of shape (N, window_size, n_features)
        labels    : np.array of shape (N,)
        scaler    : fitted StandardScaler (save this for inference in app.py)
    """
    falls_path = 'data/datasets/urfall-cam0-falls.csv'
    adls_path  = 'data/datasets/urfall-cam0-adls.csv'

    if not os.path.exists(falls_path) or not os.path.exists(adls_path):
        raise FileNotFoundError(
            "CSV files not found. Make sure urfall-cam0-falls.csv "
            "and urfall-cam0-adls.csv are in data/datasets/"
        )

    # Load CSVs (no header in URFD feature files)
    falls = pd.read_csv(falls_path, header=None)
    adls  = pd.read_csv(adls_path,  header=None)

    # Assign correct labels BEFORE combining
    falls['label'] = 1   # Fall
    adls['label']  = 0   # Non-fall (Activities of Daily Living)

    df = pd.concat([falls, adls], ignore_index=True)

    # Separate labels from features
    y_all = df['label'].values
    df_features = df.drop(columns=['label'])

    # Keep only numeric columns (drops sequence name like "fall-01", "adl-01")
    X_all = df_features.select_dtypes(include=[np.number]).values

    print(f"Total rows: {len(X_all)}, Feature dimensions: {X_all.shape[1]}")
    print(f"Fall rows: {y_all.sum()}, Non-fall rows: {(y_all==0).sum()}")

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_all)

    # Build sliding window sequences
    sequences, labels = [], []
    for i in range(0, len(X_scaled) - window_size, step):
        window_X = X_scaled[i : i + window_size]       # (window_size, n_features)
        window_y = y_all[i : i + window_size]

        sequences.append(window_X)
        # Window is labelled as FALL if ANY frame in it is a fall frame
        labels.append(1 if window_y.sum() > 0 else 0)

    sequences = np.array(sequences, dtype=np.float32)  # (N, 30, n_features)
    labels    = np.array(labels,    dtype=np.float32)  # (N,)

    print(f"\nSliding window sequences built:")
    print(f"  Shape     : {sequences.shape}")
    print(f"  Fall seqs : {int(labels.sum())} ({labels.mean()*100:.1f}%)")
    print(f"  ADL seqs  : {int((labels==0).sum())} ({(1-labels.mean())*100:.1f}%)")

    return sequences, labels, scaler


# ============================================================
# 4. Main Training Function
# ============================================================
def train_system():

    WINDOW_SIZE = 30      # frames per sequence
    STEP        = 15      # sliding step (50% overlap)
    BATCH_SIZE  = 32
    EPOCHS      = 30
    LR          = 0.001

    os.makedirs('data/processed', exist_ok=True)
    os.makedirs('models', exist_ok=True)

    # --- Build sequences from CSVs ---
    print("=" * 50)
    print("Step 1: Loading CSVs and building sequences...")
    print("=" * 50)
    sequences, labels, scaler = build_sequences(WINDOW_SIZE, STEP)

    # Save for reference / future use
    np.save('data/processed/sequences.npy', sequences)
    np.save('data/processed/labels.npy',    labels)

    # Save scaler — CRITICAL: app.py must use same scaler during inference
    import joblib
    joblib.dump(scaler, 'models/scaler.pkl')
    print("Scaler saved to models/scaler.pkl")

    # --- Train / Test Split (stratified to keep fall ratio balanced) ---
    print("\n" + "=" * 50)
    print("Step 2: Splitting into train/test sets...")
    print("=" * 50)
    X_train, X_test, y_train, y_test = train_test_split(
        sequences, labels,
        test_size=0.2,
        random_state=42,
        stratify=labels      # ensures equal fall ratio in both splits
    )
    print(f"  Train: {X_train.shape[0]} sequences")
    print(f"  Test : {X_test.shape[0]} sequences")

    # --- Convert to PyTorch Tensors ---
    X_train_t = torch.tensor(X_train)           # (N, 30, features)
    y_train_t = torch.tensor(y_train).unsqueeze(1)  # (N, 1)
    X_test_t  = torch.tensor(X_test)
    y_test_t  = torch.tensor(y_test).unsqueeze(1)

    train_dataset = TensorDataset(X_train_t, y_train_t)
    test_dataset  = TensorDataset(X_test_t,  y_test_t)

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
    test_loader  = DataLoader(test_dataset,  batch_size=BATCH_SIZE, shuffle=False)

    # --- Handle Class Imbalance ---
    # Falls are rare → give them higher loss weight so model doesn't ignore them
    n_neg = (y_train == 0).sum()
    n_pos = (y_train == 1).sum()
    pos_weight = torch.tensor([n_neg / n_pos])
    print(f"\n  Class weight for falls (pos_weight): {pos_weight.item():.2f}")

    # --- Model, Loss, Optimizer ---
    print("\n" + "=" * 50)
    print("Step 3: Training model...")
    print("=" * 50)

    input_dim = sequences.shape[2]   # number of features per frame
    model     = FallHybridModel(input_dim=input_dim)

    # BCEWithLogitsLoss is numerically more stable than BCELoss + sigmoid
    # But since our model already applies sigmoid, we use BCELoss with pos_weight manually
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=LR, weight_decay=1e-4)

    # Learning rate scheduler — reduces LR if loss stops improving
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', patience=5, factor=0.5
    )

    best_val_loss = float('inf')

    for epoch in range(EPOCHS):
        # -- Training phase --
        model.train()
        train_loss = 0.0

        for batch_X, batch_y in train_loader:
            optimizer.zero_grad()
            outputs = model(batch_X)

            # Manual pos_weight application for class imbalance
            weight = torch.where(batch_y == 1, pos_weight, torch.ones_like(batch_y))
            loss = (weight * nn.functional.binary_cross_entropy(outputs, batch_y, reduction='none')).mean()

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)  # prevent exploding gradients
            optimizer.step()
            train_loss += loss.item()

        avg_train_loss = train_loss / len(train_loader)

        # -- Validation phase --
        model.eval()
        val_loss  = 0.0
        correct   = 0
        total     = 0
        tp = fp = fn = tn = 0

        with torch.no_grad():
            for batch_X, batch_y in test_loader:
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                val_loss += loss.item()

                preds = (outputs >= 0.5).float()
                correct += (preds == batch_y).sum().item()
                total   += batch_y.size(0)

                tp += ((preds == 1) & (batch_y == 1)).sum().item()
                fp += ((preds == 1) & (batch_y == 0)).sum().item()
                fn += ((preds == 0) & (batch_y == 1)).sum().item()
                tn += ((preds == 0) & (batch_y == 0)).sum().item()

        avg_val_loss = val_loss / len(test_loader)
        accuracy     = correct / total * 100
        precision    = tp / (tp + fp + 1e-8)
        recall       = tp / (tp + fn + 1e-8)   # most important for fall detection
        f1           = 2 * precision * recall / (precision + recall + 1e-8)

        scheduler.step(avg_val_loss)

        print(f"Epoch {epoch+1:02d}/{EPOCHS} | "
              f"Train Loss: {avg_train_loss:.4f} | "
              f"Val Loss: {avg_val_loss:.4f} | "
              f"Acc: {accuracy:.1f}% | "
              f"Recall: {recall:.3f} | "
              f"F1: {f1:.3f}")

        # Save best model based on validation loss
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            torch.save({
                'model_state_dict': model.state_dict(),
                'input_dim': input_dim,
                'window_size': WINDOW_SIZE,
            }, 'models/fall_hybrid_model.pt')
            print(f"  ✓ Best model saved (val_loss={best_val_loss:.4f})")

    print("\n" + "=" * 50)
    print("Training Complete!")
    print(f"Best validation loss : {best_val_loss:.4f}")
    print("Model saved to       : models/fall_hybrid_model.pt")
    print("Scaler saved to      : models/scaler.pkl")
    print("=" * 50)


if __name__ == "__main__":
    train_system()