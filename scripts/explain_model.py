"""Print the top features driving risk, in plain language.

Usage: uv run python scripts/explain_model.py
"""

from risk_model_lib import global_feature_table, load_model


def main() -> None:
    model = load_model()
    table = global_feature_table(model)
    print(table[["feature", "odds_ratio", "sentence"]].to_string(index=False))
    print()
    print("Top 5 risk-increasing factors:")
    for _, row in table[table["coef"] > 0].head(5).iterrows():
        print(f"  - {row['sentence']}")
    print()
    print("Top 5 risk-decreasing factors:")
    for _, row in table[table["coef"] < 0].head(5).iterrows():
        print(f"  - {row['sentence']}")


if __name__ == "__main__":
    main()
