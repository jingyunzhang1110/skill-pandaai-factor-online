---
name: factors-lab-factor-mining
description: 为 jingyunzhang1110/factors_lab 挖掘新的 A 股选股因子，并直接输出可交给 common_factor import-factors 的 JSON 批次。Skill 与 factors_lab 完全独立，只共享 JSON/AST 标准；Skill 只读取自己 mother_bank/ 目录中的本地参考因子做静态去重。
---

# factors_lab 因子挖掘 Skill

本 Skill 与 factors_lab 是**两个独立项目**。二者不互相调用、不读取对方目录、不自动同步任何文件。

两边唯一的连接是共同遵守同一套：

- 新因子 JSON schema；
- canonical_expression AST；
- 字段白名单；
- 算子和参数规范。

Skill 的最终产物必须能够直接交给 factors_lab：

```powershell
python .\common_factor\top.py import-factors .\ready_for_factors_lab.json
```

## 开始生成前必须读取

- `mother_bank/MANIFEST.json`
- `mother_bank/README.md`
- `references/factors_lab_contract.md`
- `references/output_schema.md`
- `references/dedup_policy.md`
- `references/pitfalls.md`
- `references/playbook.md`
- `examples/new_factor_batch.example.json`

并把 `mother_bank/` 下除 `MANIFEST.json` 外的所有 JSON 因子文件视为“已经知道的参考因子”。

## mother_bank 的含义

`mother_bank/` 是 Skill 自己的本地参考库。

初始文件：

```text
mother_bank/clean_seed_factor_bank.json
```

保存最初 549 个因子的唯一因子快照。

以后人类用户可以把新的、已经准备好用于参考的因子 JSON **直接放在同一个 `mother_bank/` 目录下**，例如：

```text
mother_bank/
├─ clean_seed_factor_bank.json
├─ added_20261007_001.json
├─ added_20261012_001.json
└─ MANIFEST.json
```

validator 会自动扫描这些文件，把初始 549 和后来加入的参考因子一起用于去重。

Skill 不会去 factors_lab 拉取、刷新或同步这些文件。如何人工维护见根目录 `HUMAN_GUIDE.zh-CN.md`。

## 硬性约束

1. 因子公式唯一权威表示是 `canonical_expression`。
2. 字段、AST kind、operator、参数范围只能使用 `references/factors_lab_contract.md` 明确列出的内容。
3. 禁止自行创造字段别名、技术指标名、券商研报宏、平台函数或新算子。
4. 禁止未来收益、未来价格、负 lag、未来标签以及因子日不可获得的信息。
5. 禁止 LLM 生成 `factor_id`、`expression_fingerprint`、`duplicate_type`、`representation`、`parse_error`、`import_batch`。
6. 顶层 JSON 只能有 `schema_version`、`batch_name`、`source`、`records`。
7. 每条 record 只能有：`source_record_id`、`name`、`source`、`source_ref`、`formula_provenance`、`original_formula`、`economic_rationale`、`source_constraints`、`canonical_expression`。
8. `source_record_id` 必须批内唯一并尽量全局唯一。
9. AST 节点数 ≤ 64、深度 ≤ 12、lookback ≤ 2520 个交易日。
10. 与 `mother_bank/` 中任一参考因子或本批候选完全相同的 canonical AST 直接淘汰。
11. 静态可证明排序等价的因子直接淘汰；乘 -1、再套 rank/zscore 或改名称不能算新因子。
12. 同一批次不允许只改窗口或数字常数的 parameter-only 变体。
13. 默认禁止 `IF(condition, signal, 0)` / `IF(condition, 0, signal)`。
14. 分母可能接近 0 或跨 0 时必须重新设计，或在 `source_constraints` 中明确风险；禁止用随意 epsilon 掩盖。
15. 想法如果不能只用支持字段/算子准确表达，直接放弃。
16. 只有通过 `scripts/validate_candidates.py` 的批次才允许交给 factors_lab。

## 生成与验证

直接按 `examples/new_factor_batch.example.json` 生成：

```bash
python scripts/validate_candidates.py \
  --input generated_batch.json \
  --output ready_for_factors_lab.json \
  --report audit_report.json
```

只有 `ready_for_factors_lab.json` 才是正式输出。

## 项目边界

```text
Skill 项目
mother_bank/ 本地参考库
        ↓
LLM 挖掘 + 静态校验
        ↓
ready_for_factors_lab.json
        │
        │ 人工复制这个文件
        ▼
factors_lab 项目
import-factors
        ↓
RAW / factors.sqlite / single_factor / multi_factor
```

Skill 不分配正式 16 位 ID，不访问 factors_lab 的 RAW，也不维护 factors_lab 的运行状态。
