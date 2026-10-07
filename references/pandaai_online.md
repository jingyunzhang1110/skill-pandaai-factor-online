# Optional PandaAI online diagnostics

PandaAI is not the expression authority in this fork. A candidate first has to pass factors_lab validation.

## Safe sequence

1. Generate canonical AST candidates.
2. Run `validate_candidates.py`.
3. Run `export_pandaai_manifest.py` on the accepted output.
4. Review the export report. Candidates marked not translatable remain valid local candidates but must not be silently rewritten.
5. If online execution is desired, the user authenticates interactively with `pandaai-cli login`.
6. Run the generated manifest with `scripts/batch.py` using explicit dates, adjustment cycle and hypotheses count.

## Why only a subset is exported

The two systems do not share every field or operator. The exporter intentionally supports only a conservative intersection. It rejects unsupported nodes rather than approximating them.

## Credentials

Never ask for, print, store or commit phone numbers, passwords, tokens or PandaAI config contents.

## Interpretation

PandaAI data, universe, PIT handling and execution assumptions may differ from factors_lab. Online metrics are a source-stage diagnostic, not a substitute for factors_lab formal evaluation.
