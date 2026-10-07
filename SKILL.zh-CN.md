---
name: factors-lab-factor-mining
description: 为 jingyunzhang1110/factors_lab 挖掘新的 A 股选股因子，只允许使用母库支持的字段和 AST 算子，并在输出前严格排除完全重复、排序等价、参数-only、未来信息和其他不兼容候选。
---

# factors_lab 纯因子挖掘 Skill

本 Skill 只负责**提出新因子并做静态准入审计**。不负责第三方平台、不负责在线回测、不负责账户登录、不负责提交因子，也不绑定任何特定 AI 运行时。

开始挖掘前必须读取：

- `mother_bank/MANIFEST.json`
- `references/factors_lab_contract.md`
- `references/dedup_policy.md`
- `references/pitfalls.md`
- `references/playbook.md`
- `references/output_schema.md`

## 硬性规则

1. 唯一权威公式格式是 factors_lab 的 `canonical_expression` AST。
2. 只能使用 `references/factors_lab_contract.md` 明确列出的字段、AST kind 和算子。
3. 禁止自行发明字段别名、平台宏、技术指标名或未注册财务字段。
4. 禁止未来收益、未来价格、负 lag 和任何因子日不可得的信息。
5. 不得自行分配正式 16 位 `factor_id`。
6. 候选对外称为“合格”之前，必须通过 `scripts/validate_candidates.py`。
7. 与 549 母库完全重复的候选直接淘汰。
8. 与母库或同批候选静态可证明排序等价的候选直接淘汰；方向 0/1 不会把同一个暴露变成两个因子。
9. 同一生成批次默认禁止只改窗口、常数或轻微参数的 parameter-only 变体。
10. 默认禁止 `IF(condition, signal, 0)` 和 `IF(condition, 0, signal)` 这类会制造大面积零值并列的条件因子。
11. 优先生成机制清楚、表达式简洁、可解释的候选；复杂嵌套必须有明确增量意义。
12. 分母可能接近 0 或跨 0 时必须重新设计或明确标注风险，不得用随意 epsilon 掩盖。
13. 被拒绝的候选要保留在审计报告里，不能悄悄改公式后当作原候选继续。

## 挖掘流程

### 第一步：先看母库，再想新因子

不要只查名字。要检查 549 因子中是否已经存在相同机制、相同排序暴露或明显代理变量。

### 第二步：先写机制，再写公式

每个候选至少明确：

- 因子族；
- 经济/行为逻辑；
- higher is better 或 lower is better；
- 使用字段；
- 时间尺度；
- 主要失效场景；
- 为什么它不是母库已有因子的改名或参数变体。

### 第三步：保证机制多样性

优先跨不同族探索，例如：

- 动量 / 反转；
- 波动率 / 偏度 / 分布形态；
- 流动性 / 换手；
- 价量交互；
- 价值；
- 盈利能力 / 质量；
- 现金流质量 / 应计；
- 成长；
- 杠杆；
- 资本开支 / 投资；
- 相对基准或事件结构；
- 必要时的行业/板块中性化。

同一批次不要用大量不同窗口填满。

### 第四步：翻译成 factors_lab canonical AST

如果一个想法离开不支持的字段或算子就无法保持原意，直接放弃，不要近似成另一条因子。

### 第五步：强制审计

```bash
python scripts/validate_candidates.py \
  --input candidate_batch.json \
  --output accepted_candidates.json \
  --report audit_report.json
```

只有 `accepted_candidates.json` 中的条目才是本 Skill 的正式输出。

### 第六步：到此停止

本 Skill 不评价收益，也不负责选择最终有效因子。后续由 factors_lab 负责：

`分配ID → ensure-values → single_factor → 经验相关性/结果去重 → FINAL_TEST → multi_factor`。

## 去重原则

除 canonical AST 完全一致外，还要拒绝可静态证明的排序等价，例如：

- `x`、`rank(x)`、`zscore(x)`、正比例缩放；
- `x` 与 `-x` 这种正反排序关系；
- 正的仿射变换；
- 可以证明为正值时的 `log(x)`、`sqrt(x)`；
- 可证明非负时多余的 `abs(x)`；
- 两边都为正时的正比率及其倒数；
- `SUM(condition,N)/N` 与 `MEAN(condition,N)`；
- 同一批次中仅窗口或数字常数不同的同结构候选。

静态检查无法覆盖所有经济语义重复，因此模型仍必须主动做机制层去重。
