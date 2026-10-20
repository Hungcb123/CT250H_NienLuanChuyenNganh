"""Entrypoint for the canonical close-v1 training/evaluation pipeline.

Run from the repository root: python3 ml/train_regime_model.py
Requires real CSVs; never substitutes synthetic prices for missing data.
"""
from regime_pipeline import feature_frame, train


def calculate_technical_features(df):
    return feature_frame(df)


def train_and_export_onnx(output_dir="backend/src/main/resources/models"):
    return train("VNINDEX", "stock_regime", output_dir)


def train_gold_model(output_dir="backend/src/main/resources/models"):
    # Research artifact only: runtime rejects GC for a domestic GOLD_SJC portfolio.
    return train("GC", "gold_trend", output_dir)


if __name__ == "__main__":
    train_and_export_onnx()
    train_gold_model()
