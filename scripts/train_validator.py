"""
Training and ONNX Export Script for FSOC Beacon AI Validator.

Trains a compact CNN on 32x32 beacon vs clutter crops and exports to ONNX.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import time
import cv2
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import onnxruntime as ort


class CropDataset(Dataset):
    def __init__(self, root_dir: Path):
        self.samples = []
        pos_dir = root_dir / "1_beacon"
        neg_dir = root_dir / "0_clutter"

        if pos_dir.exists():
            for p in pos_dir.glob("*.png"):
                self.samples.append((str(p), 1.0))
        if neg_dir.exists():
            for p in neg_dir.glob("*.png"):
                self.samples.append((str(p), 0.0))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            img = np.zeros((32, 32), dtype=np.uint8)
        img = img.astype(np.float32) / 255.0
        tensor = torch.from_numpy(img).unsqueeze(0)  # (1, 32, 32)
        return tensor, torch.tensor([label], dtype=torch.float32)


class BeaconClassifierCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, padding=1),
            nn.BatchNorm2d(16),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),  # 16x16

            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),  # 8x8

            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((2, 2)),  # (B, 64, 2, 2)
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64 * 2 * 2, 32),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(32, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        feat = self.features(x)
        out = self.classifier(feat)
        return out


def train_and_export(data_dir: Path, output_onnx: Path, epochs: int = 6, batch_size: int = 32):
    train_ds = CropDataset(data_dir / "train")
    val_ds = CropDataset(data_dir / "val")

    print(f"Loaded {len(train_ds)} train crops, {len(val_ds)} val crops.")
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = BeaconClassifierCNN().to(device)

    criterion = nn.BCELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

    print(f"Training on device: {device} for {epochs} epochs...")
    for epoch in range(epochs):
        model.train()
        total_loss = 0.0
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            preds = model(x)
            loss = criterion(preds, y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(x)

        train_loss = total_loss / len(train_ds)

        # Validation
        model.eval()
        correct = 0
        total = 0
        with torch.no_grad():
            for x, y in val_loader:
                x, y = x.to(device), y.to(device)
                preds = model(x)
                predicted_labels = (preds >= 0.5).float()
                correct += (predicted_labels == y).sum().item()
                total += len(y)

        val_acc = (correct / total * 100.0) if total > 0 else 0.0
        print(f"Epoch {epoch + 1}/{epochs} - Train Loss: {train_loss:.4f}, Val Acc: {val_acc:.2f}%")

    # Export to ONNX
    model.eval()
    dummy_input = torch.randn(1, 1, 32, 32, device=device)
    output_onnx.parent.mkdir(parents=True, exist_ok=True)

    print(f"Exporting ONNX model to {output_onnx}...")
    torch.onnx.export(
        model,
        dummy_input,
        str(output_onnx),
        export_params=True,
        opset_version=14,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}},
        dynamo=False,
    )

    # Verify with ONNX Runtime
    session = ort.InferenceSession(str(output_onnx))
    test_input = np.random.randn(1, 1, 32, 32).astype(np.float32)
    ort_out = session.run(["output"], {"input": test_input})[0]
    print(f"ONNX model verified successfully! Sample prediction shape: {ort_out.shape}, value: {ort_out[0][0]:.4f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=str, default="data/dataset")
    parser.add_argument("--output", type=str, default="models/beacon_validator.onnx")
    parser.add_argument("--epochs", type=int, default=6)
    args = parser.parse_args()

    train_and_export(Path(args.data_dir), Path(args.output), epochs=args.epochs)
