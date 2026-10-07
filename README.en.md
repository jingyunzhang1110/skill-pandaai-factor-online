# factors_lab-compatible PandaAI Factor Skill

This fork of `quantskills/skill-pandaai-factor-online` is specialized for `jingyunzhang1110/factors_lab`.

The primary representation is now the factors_lab canonical AST. The bundled 549-factor mother bank is the deduplication baseline. PandaAI remains optional as a secondary online diagnostic only for candidates that can be translated losslessly into a safe PandaAI formula subset.

Key guarantees:

- only factors_lab fields and AST operators are allowed;
- no future fields or negative lags;
- exact and rank-equivalent duplicates against the mother bank are rejected;
- exact/rank-equivalent duplicates inside a batch are rejected;
- parameter-only variants inside one batch are rejected by default;
- zero-mask conditionals such as `IF(condition, signal, 0)` are rejected by default;
- output canonical expressions match the factors_lab mother-bank representation;
- PandaAI syntax never defines the research contract.

Read `SKILL.md` or `SKILL.zh-CN.md` for the full workflow.
