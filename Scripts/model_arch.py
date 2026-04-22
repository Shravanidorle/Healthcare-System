import torch
import torch.nn as nn
import torch.nn.functional as F

class NMMCU(nn.Module):
    """Non-Monotonic Mish Cubic Unit [cite: 114]"""
    def forward(self, x):
        mish = x * torch.tanh(F.softplus(x))
        return mish - (x ** 3)

class FallHybridModel(nn.Module):
    def __init__(self, input_dim):
        super(FallHybridModel, self).__init__()
        self.nmmcu = NMMCU()
        
        # Temporal CNN [cite: 110]
        self.conv1 = nn.Conv1d(in_channels=input_dim, out_channels=64, kernel_size=3)
        
        # LSTM Layer [cite: 122]
        self.lstm = nn.LSTM(input_size=64, hidden_size=128, num_layers=2, batch_first=True)
        
        # Fully Connected [cite: 132]
        self.fc = nn.Linear(128, 1) # Output: Probability score Y 

    def forward(self, x):
        # x shape: (batch, seq_len, features)
        x = x.transpose(1, 2)
        x = self.nmmcu(self.conv1(x))
        x = x.transpose(1, 2)
        _, (hn, _) = self.lstm(x)
        out = torch.sigmoid(self.fc(hn[-1]))
        return out