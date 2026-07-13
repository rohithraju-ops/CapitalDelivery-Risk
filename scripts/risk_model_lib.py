"""Shared helpers for extracting logistic-regression contributions in plain language.

Used by explain_model.py (global "top features driving risk") and score_projects.py
(per-project one-sentence explanations) so both stay consistent with each other.
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / "data" / "processed" / "risk_model.joblib"

CATEGORICAL_FEATURES = ["project_type_bucketed", "road_system_bucketed", "district_bucketed"]
NUMERIC_FEATURES = ["log_allocated_budget"]
ALL_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES


def load_model() -> Pipeline:
    return joblib.load(MODEL_PATH)


def global_feature_table(model: Pipeline) -> pd.DataFrame:
    """One row per one-hot/numeric feature the fitted model actually has a coefficient for,
    with the odds ratio and a plain-language sentence relative to each feature's reference
    category (the one OneHotEncoder(drop='first') dropped)."""
    prep = model.named_steps["prep"]
    clf = model.named_steps["clf"]
    feature_names = prep.get_feature_names_out()
    coefs = clf.coef_[0]

    cat_encoder = prep.named_transformers_["cat"]
    reference_categories = {
        col: cats[0] for col, cats in zip(prep.transformers_[0][2], cat_encoder.categories_)
    }

    rows = []
    for raw_name, coef in zip(feature_names, coefs):
        odds_ratio = float(np.exp(coef))
        if raw_name.startswith("cat__"):
            # raw_name looks like "cat__<column>_<category>"; recover column by matching
            # against the known categorical columns since categories can contain underscores.
            stripped = raw_name[len("cat__"):]
            column = next(c for c in reference_categories if stripped.startswith(c + "_"))
            category = stripped[len(column) + 1:]
            reference = reference_categories[column]
            direction = "higher" if coef > 0 else "lower"
            sentence = (
                f"{column}='{category}' carries {odds_ratio:.2f}x the odds of being flagged "
                f"at-risk compared to {column}='{reference}' ({direction} risk)."
            )
            rows.append({"feature": raw_name, "column": column, "category": category, "coef": coef,
                         "odds_ratio": odds_ratio, "sentence": sentence})
        elif "missingindicator" in raw_name:
            # Checked before the generic "num__" prefix below: SimpleImputer's indicator
            # columns are also emitted under the "num__" namespace by ColumnTransformer.
            rows.append({"feature": raw_name, "column": "log_allocated_budget_missing", "category": None,
                         "coef": coef, "odds_ratio": odds_ratio,
                         "sentence": "Indicator for projects with no allocated-budget figure to compute a size feature from."})
        elif raw_name.startswith("num__"):
            direction = "increases" if coef > 0 else "decreases"
            trend_note = " — bigger projects trend riskier" if coef > 0 else ""
            sentence = (
                f"Each one-unit increase in log(allocated budget) {direction} the odds of "
                f"being flagged at-risk by {odds_ratio:.2f}x{trend_note}."
            )
            rows.append({"feature": raw_name, "column": "log_allocated_budget", "category": None,
                         "coef": coef, "odds_ratio": odds_ratio, "sentence": sentence})

    return pd.DataFrame(rows).sort_values("coef", key=lambda s: s.abs(), ascending=False).reset_index(drop=True)


def _short_factor_description(row: pd.Series) -> str:
    # category ends up NaN (not None) once mixed into a pandas object column, so check with
    # pd.notna rather than `is not None`.
    if pd.notna(row["category"]):
        return f"{row['column']}='{row['category']}'"
    return row["column"]


def score_and_explain(model: Pipeline, df: pd.DataFrame, top_k: int = 2) -> pd.DataFrame:
    """Score every row in df and attach a one-sentence, per-project explanation built from
    that row's top-k largest-magnitude feature contributions to the logit — an exact
    decomposition (contribution = coefficient x feature value), not an approximation."""
    prep = model.named_steps["prep"]
    clf = model.named_steps["clf"]
    coefs = clf.coef_[0]
    intercept = clf.intercept_[0]
    feature_names = prep.get_feature_names_out()
    feature_lookup = global_feature_table(model).set_index("feature")

    X_transformed = prep.transform(df[ALL_FEATURES])
    if hasattr(X_transformed, "toarray"):
        X_transformed = X_transformed.toarray()
    contributions = X_transformed * coefs
    logits = contributions.sum(axis=1) + intercept
    probabilities = 1.0 / (1.0 + np.exp(-logits))

    explanations = []
    for row_contrib in contributions:
        nonzero_idx = np.flatnonzero(np.abs(row_contrib) > 1e-9)
        top_idx = nonzero_idx[np.argsort(-np.abs(row_contrib[nonzero_idx]))][:top_k]
        factors = []
        for idx in top_idx:
            fname = feature_names[idx]
            if fname not in feature_lookup.index:
                continue
            desc = _short_factor_description(feature_lookup.loc[fname])
            direction = "raises" if row_contrib[idx] > 0 else "lowers"
            factors.append(f"{desc} ({direction} risk)")
        explanations.append("; ".join(factors) if factors else "no strong individual driver")

    return pd.DataFrame({
        "upc": df["upc"].values,
        "risk_probability": probabilities,
        "risk_score": np.round(probabilities * 100).astype(int),
        "top_factors": explanations,
    })
