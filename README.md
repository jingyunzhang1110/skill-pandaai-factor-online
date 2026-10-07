# factors_lab 因子挖掘 Skill

这是一个**纯因子挖掘 Skill**，专门为 `jingyunzhang1110/factors_lab` 生成新的 A 股选股因子候选。

它不负责在线回测、不负责向任何第三方平台提交因子，也不绑定 Codex、Claude、Cursor 或其他运行时。它只做三件事：

1. 基于清晰的经济/市场机制提出新的因子假设；
2. 把候选写成 factors_lab 原生 canonical AST；
3. 在输出前对字段、算子、未来信息、母库重复和批内重复做严格审计。

## 核心约束

- 内置当前 factors_lab 的 549 因子母库快照；
- 只能使用当前 factors_lab 已支持的字段、AST kind 与算子；
- 禁止未来字段、负 lag、非有限常数和非法窗口；
- 必须检查：
  - canonical AST 完全重复；
  - 与母库的静态可证明排序等价重复；
  - 批内完全/排序等价重复；
  - 同批只改窗口或常数的 parameter-only 变体；
  - `IF(condition, signal, 0)` 这类大面积 0 并列风险；
- 方向元数据不能把同一个暴露包装成“新因子”；
- 不给候选分配正式 16 位 factor_id，ID 仍由 factors_lab 母库流程负责。

## 推荐工作流

1. 读取 `SKILL.zh-CN.md`；
2. 读取 `mother_bank/MANIFEST.json`、`references/factors_lab_contract.md`、`references/dedup_policy.md`、`references/pitfalls.md` 和 `references/playbook.md`；
3. 先设计机制不同的候选，再写公式；
4. 按 `references/output_schema.md` 输出 `candidate_batch.json`；
5. 强制运行：

```bash
python scripts/validate_candidates.py \
  --input candidate_batch.json \
  --output accepted_candidates.json \
  --report audit_report.json
```

只有 `accepted_candidates.json` 中的候选才算通过本 Skill 的静态准入。

## 目录

```text
SKILL.md
SKILL.zh-CN.md
mother_bank/
  clean_seed_factor_bank.json
  MANIFEST.json
references/
  factors_lab_contract.md
  dedup_policy.md
  pitfalls.md
  playbook.md
  output_schema.md
scripts/
  validate_candidates.py
  refresh_mother_bank.py
  bootstrap.py
  selftest.py
tests/
  test_validate_candidates.py
examples/
  candidate_batch.example.json
```

## 边界

这个 Skill **不做回测**，也不根据历史收益给候选打分。真正的因子值计算、单因子评价、去重、最终测试和多因子组合仍交给 factors_lab。

## 母库更新

当 factors_lab 母库发生变化后，用：

```bash
python scripts/refresh_mother_bank.py \
  --source <factors_lab>/common_factor/catalog/clean_seed_factor_bank.json
```

更新快照后重新执行自检，再开始新的挖掘批次。
