---
name: factors-lab-factor-mining
description: 为 jingyunzhang1110/factors_lab 挖掘新的 A 股选股因子，并直接输出可交给 common_factor import-factors 的 JSON 批次。只能使用 Skill 内固定的 factors_lab 字段和 AST 算子规范，输出前必须排除非法 AST、未来信息、完全重复、排序等价、参数-only 和其他不兼容候选。
---

# factors_lab 因子挖掘 Skill

本 Skill 的最终产物只有一种：**可以直接导入 factors_lab 新待筛选因子库的 JSON**。

最终输出必须能够直接执行：

```powershell
python .\common_factor\top.py import-factors .\ready_for_factors_lab.json
```

中间不允许人工再改格式、补 ID 或改 AST。

开始生成前必须读取：

- `mother_bank/MANIFEST.json`
- `references/factors_lab_contract.md`
- `references/output_schema.md`
- `references/dedup_policy.md`
- `references/pitfalls.md`
- `references/playbook.md`
- `examples/new_factor_batch.example.json`

## 硬性约束

1. 因子公式唯一权威表示是 `canonical_expression`，必须严格使用 factors_lab 当前 AST。
2. 字段、AST kind、operator、参数范围只能使用 `references/factors_lab_contract.md` 明确列出的内容。
3. 禁止自行创造字段别名、技术指标名、券商研报宏、平台函数或新算子。
4. 禁止未来收益、未来价格、负 lag、未来标签以及因子日不可获得的信息。
5. **禁止 LLM 生成** `factor_id`、`expression_fingerprint`、`duplicate_type`、`representation`、`parse_error`、`import_batch`。这些全部由 factors_lab 管理。
6. 顶层 JSON 只能有 `schema_version`、`batch_name`、`source`、`records`。
7. 每条记录只能有：`source_record_id`、`name`、`source`、`source_ref`、`formula_provenance`、`original_formula`、`economic_rationale`、`source_constraints`、`canonical_expression`。
8. `source_record_id` 必须批内唯一，推荐使用 `FM-YYYYMMDD-批次号-####` 一类全局不易冲突的格式。
9. AST 静态上限与 factors_lab 一致：节点数 ≤ 64、深度 ≤ 12、lookback ≤ 2520 个交易日。
10. 与母库或本批完全相同的 canonical AST 直接淘汰。
11. 静态可证明排序等价的因子直接淘汰；乘 -1、改方向说明、再套 rank/zscore 不能算新因子。
12. 同一批次不允许只改窗口或数字常数的 parameter-only 变体。
13. 默认禁止 `IF(condition, signal, 0)` / `IF(condition, 0, signal)` 这种大面积制造 0 并列的条件因子。
14. 分母可能接近 0 或跨 0 时必须重新设计，或者在 `source_constraints` 中明确风险；禁止随意加 epsilon 掩盖问题。
15. 一个想法如果离开未支持字段/算子就无法表达，直接放弃，不得近似成另一条信号。
16. 只有通过 `scripts/validate_candidates.py` 的批次才允许交给 factors_lab。

## 生成顺序

先明确经济/行为机制、预期方向、时间尺度、所需字段、主要失效场景以及与母库的区别，再写 AST。不要先堆公式再补故事。

直接按照 `examples/new_factor_batch.example.json` 生成最终格式。`original_formula` 用于人类阅读和来源追踪，真正决定计算语义的是 `canonical_expression`。

每批强制执行：

```bash
python scripts/validate_candidates.py \
  --input generated_batch.json \
  --output ready_for_factors_lab.json \
  --report audit_report.json
```

只有 `ready_for_factors_lab.json` 才能进入 factors_lab。

## 与 factors_lab 的边界

```text
ready_for_factors_lab.json
→ common_factor import-factors
→ 新建 append-only RAW 分片
→ factors.sqlite
→ single_factor
→ accepted / 经验去重
→ multi_factor
```

Skill 到静态准入为止，不分配正式 16 位 ID，也不直接修改 factors_lab 的 RAW。
