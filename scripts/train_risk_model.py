"""Train and persist the final risk-scoring model (logistic regression — see
reports/figures/model_comparison_metrics.csv and docs/risk_model.md for why).

Usage: uv run python scripts/train_risk_model.py

Reports the same stratified 5-fold CV metrics as scripts/compare_models.py (the honest
number to quote, given several small project_type subgroups make a single held-out split
noisy), then refits on the full labeled population — since scoring, not evaluation, is the
point of the persisted model.
"""

from pathlib import Path

import duckdb
import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "processed" / "capital_delivery_risk.duckdb"
MODEL_PATH = ROOT / "data" / "processed" / "risk_model.joblib"

CATEGORICAL_FEATURES = ["project_type_bucketed", "road_system_bucketed", "district_bucketed"]
NUMERIC_FEATURES = ["log_allocated_budget"]
ALL_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES


def build_pipeline() -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            # drop='first' so each category's coefficient reads as "vs. a reference
            # category" — needed for a clean one-sentence explanation per feature.
            ("cat", OneHotEncoder(drop="first", handle_unknown="ignore"), CATEGORICAL_FEATURES),
            (
                "num",
                Pipeline([
                    ("impute", SimpleImputer(strategy="median", add_indicator=True)),
                    ("scale", StandardScaler()),
                ]),
                NUMERIC_FEATURES,
            ),
        ]
    )
    return Pipeline([("prep", preprocessor), ("clf", LogisticRegression(max_iter=1000, random_state=42))])


def main() -> None:
    con = duckdb.connect(str(DB_PATH))
    labeled = con.execute("SELECT * FROM model_features WHERE has_label").df()
    con.close()

    X = labeled[ALL_FEATURES]
    y = labeled["at_risk"].astype(int)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_results = cross_validate(build_pipeline(), X, y, cv=cv, scoring=["roc_auc", "precision", "recall", "f1"])
    print("5-fold CV performance (final model, logistic regression):")
    for metric in ["roc_auc", "precision", "recall", "f1"]:
        scores = cv_results[f"test_{metric}"]
        print(f"  {metric}: {scores.mean():.3f} +/- {scores.std():.3f}")

    final_pipeline = build_pipeline()
    final_pipeline.fit(X, y)
    joblib.dump(final_pipeline, MODEL_PATH)
    print(f"\nsaved fitted model to {MODEL_PATH}")


if __name__ == "__main__":
    main()
