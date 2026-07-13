"""Compare candidate models for the risk-scoring layer with stratified 5-fold CV.

Usage: uv run python scripts/compare_models.py

Not a single train/test split — with ~4,700 labeled rows, real class imbalance, and
several small project_type subgroups, a single split gives a noisy read on which model
actually generalizes best. Outputs a metric table (printed + logged) and two plots in
reports/figures/.
"""

from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import RocCurveDisplay, roc_curve, auc
from sklearn.model_selection import StratifiedKFold, cross_val_predict, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "processed" / "capital_delivery_risk.duckdb"
FIGURES_DIR = ROOT / "reports" / "figures"

CATEGORICAL_FEATURES = ["project_type_bucketed", "road_system_bucketed", "district_bucketed"]
NUMERIC_FEATURES = ["log_allocated_budget"]

CANDIDATES = {
    "logistic_regression": LogisticRegression(max_iter=1000, random_state=42),
    "decision_tree": DecisionTreeClassifier(max_depth=5, random_state=42),
    "random_forest": RandomForestClassifier(n_estimators=300, max_depth=8, random_state=42),
    "gradient_boosting": GradientBoostingClassifier(random_state=42),
}


def load_training_data() -> pd.DataFrame:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = con.execute("SELECT * FROM model_features WHERE has_label").df()
    con.close()
    return df


def build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
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


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    df = load_training_data()
    X = df[CATEGORICAL_FEATURES + NUMERIC_FEATURES]
    y = df["at_risk"].astype(int)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scoring = ["roc_auc", "precision", "recall", "f1"]

    results = []
    fig_roc, ax_roc = plt.subplots(figsize=(6, 6))

    for name, estimator in CANDIDATES.items():
        pipeline = Pipeline([("prep", build_preprocessor()), ("clf", estimator)])

        cv_results = cross_validate(pipeline, X, y, cv=cv, scoring=scoring)
        row = {"model": name}
        for metric in scoring:
            key = f"test_{metric}"
            row[f"{metric}_mean"] = cv_results[key].mean()
            row[f"{metric}_std"] = cv_results[key].std()
        results.append(row)

        # Out-of-fold predicted probabilities give a fair, pooled ROC curve for this model.
        oof_proba = cross_val_predict(pipeline, X, y, cv=cv, method="predict_proba")[:, 1]
        fpr, tpr, _ = roc_curve(y, oof_proba)
        roc_auc = auc(fpr, tpr)
        ax_roc.plot(fpr, tpr, label=f"{name} (AUC={roc_auc:.3f})")

    ax_roc.plot([0, 1], [0, 1], linestyle="--", color="gray", label="chance")
    ax_roc.set_xlabel("False Positive Rate")
    ax_roc.set_ylabel("True Positive Rate")
    ax_roc.set_title("Out-of-fold ROC curves (5-fold CV) by candidate model")
    ax_roc.legend(loc="lower right")
    fig_roc.tight_layout()
    fig_roc.savefig(FIGURES_DIR / "model_comparison_roc.png", dpi=150)

    results_df = pd.DataFrame(results).set_index("model")
    print(results_df.to_string())
    results_df.to_csv(FIGURES_DIR / "model_comparison_metrics.csv")

    fig_bar, ax_bar = plt.subplots(figsize=(8, 5))
    metrics_to_plot = ["roc_auc", "precision", "recall", "f1"]
    x = np.arange(len(results_df))
    width = 0.2
    for i, metric in enumerate(metrics_to_plot):
        ax_bar.bar(
            x + i * width,
            results_df[f"{metric}_mean"],
            width,
            yerr=results_df[f"{metric}_std"],
            label=metric,
            capsize=3,
        )
    ax_bar.set_xticks(x + width * 1.5)
    ax_bar.set_xticklabels(results_df.index, rotation=20, ha="right")
    ax_bar.set_ylabel("score")
    ax_bar.set_title("5-fold CV metric comparison (mean +/- std)")
    ax_bar.legend()
    fig_bar.tight_layout()
    fig_bar.savefig(FIGURES_DIR / "model_comparison_metrics.png", dpi=150)

    print(f"\nsaved plots to {FIGURES_DIR}")


if __name__ == "__main__":
    main()
