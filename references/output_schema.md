# Candidate output schema

The AI should write UTF-8 JSON in this shape:

```json
{
  "schema_version": 1,
  "source": "deepseek-harness-pandaai-skill",
  "allow_parameter_variants": false,
  "allow_zero_mask": false,
  "candidates": [
    {
      "name": "example_candidate",
      "source_code": "DS-0001",
      "family": "momentum",
      "direction": 1,
      "hypothesis": "medium-horizon continuation after controlling short-horizon noise",
      "canonical_expression": {
        "kind": "binary",
        "operator": "sub",
        "left": {
          "kind": "binary",
          "operator": "div",
          "left": {"kind": "feature", "name": "close", "lag": 0},
          "right": {
            "kind": "rolling",
            "operator": "mean",
            "operand": {"kind": "feature", "name": "close", "lag": 0},
            "window": 60
          }
        },
        "right": {"kind": "constant", "value": 1}
      }
    }
  ]
}
```

`direction=1` means higher is better; `direction=0` means lower is better.

Do not assign a formal `factor_id`.

The validator adds:

- `original_formula` and `normalized_formula` rendered from the AST;
- `expression_fingerprint`;
- `representation: "ast"`;
- `metrics` including nodes/depth/operators/lookback;
- `audit` and `data_readiness`;
- warnings and duplicate diagnostics in the report.

The canonical AST is always authoritative. Human-readable formula text must never be used to bypass AST validation.
