# factors_lab 兼容版 PandaAI 因子 Skill

这是从 `quantskills/skill-pandaai-factor-online` fork 后重构的专用版本，服务于 `jingyunzhang1110/factors_lab`。

目标只有一个：**让 AI 生成的新因子从出生起就能进入 factors_lab 的母库表达体系，同时保留 PandaAI 在线回测作为可选的二级筛选。**

## 核心约束

- 内置当前 factors_lab 的 549 因子母库快照；
- 生成表达式必须使用 factors_lab canonical AST；
- 只能使用当前 factors_lab 已支持的字段、AST kind 和算子；
- 禁止未来字段、负 lag、非有限常数和无效窗口；
- 在输出前必须同时检查：
  - 与 549 母库的 canonical AST 完全重复；
  - 与 549 母库的横截面排序等价重复；
  - 同一候选批次内部的完全/排序等价重复；
  - 同一批中只改窗口或常数的参数-only 变体；
  - `IF(condition, signal, 0)` / `IF(condition, 0, signal)` 这类大规模 0 并列风险；
- PandaAI 只作为可选在线诊断，不是母库语法的权威来源；
- 因子是否最终进入 factors_lab，仍由 factors_lab 自己的单因子/多因子流程决定。

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
  pandaai_online.md
scripts/
  validate_candidates.py
  export_pandaai_manifest.py
  batch.py
  analyze.py
  bootstrap.py
  selftest.py
tests/
  test_validate_candidates.py
examples/
  candidate_batch.example.json
```

## 推荐工作流

1. AI 读取 `SKILL.zh-CN.md` 和母库；
2. 先提出机制不同的候选，不做参数暴力枚举；
3. 输出 `candidate_batch.json`；
4. 强制运行：

```bash
python scripts/validate_candidates.py \
  --input candidate_batch.json \
  --output accepted_candidates.json \
  --report audit_report.json
```

5. 只有 `accepted_candidates.json` 里的候选才算合格；
6. 如需 PandaAI 在线筛选，再运行：

```bash
python scripts/export_pandaai_manifest.py \
  --input accepted_candidates.json \
  --output pandaai_candidates.txt \
  --report pandaai_export_report.json
```

7. 对成功导出的候选，可继续复用原项目成熟的 `scripts/batch.py` 在线创建/回测；
8. 最终通过者再交回 factors_lab 做本地正式评估。

## 关于 PandaAI

PandaAI 的字段、算子、股票池、数据口径与 factors_lab 不完全一致。因此本项目不再允许 AI 直接写 PandaAI 公式作为主输出。`export_pandaai_manifest.py` 只对可安全等价转换的 AST 子集生成 PandaAI 公式；不能转换的候选仍可用于 factors_lab，但不会被送去 PandaAI。

## 来源与许可

本仓库 fork 自 `quantskills/skill-pandaai-factor-online`，保留原仓库 LICENSE。此次改造删除了 Codex、Claude、Cursor、Hermes 等运行时专用配置，并将研究契约改为 factors_lab-first。
