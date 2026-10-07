---
name: factors-lab-pandaai-factor-source
description: 为 jingyunzhang1110/factors_lab 生成严格兼容、经过母库去重的 A 股因子候选；可选使用 PandaAI 在线回测做二级筛选。主输出必须是 factors_lab canonical AST，而不是 PandaAI 私有公式。
---

# factors_lab 专用因子挖掘 Skill

## 1. 角色

你的任务是为 `factors_lab` **提出新的因子假设**，不是为了凑数量生成大量公式变体。

最终目标链路：

```text
机制/文献/市场微观结构假设
        ↓
生成 factors_lab canonical AST
        ↓
549 母库 + 批内严格去重
        ↓
可选：PandaAI 在线诊断
        ↓
factors_lab 单因子正式评价
        ↓
accepted / dedup / multi_factor
```

PandaAI 是可选筛选器，`factors_lab` 才是最终兼容性和研究评价标准。

## 2. 开始任何生成任务前必须读取

按顺序读取：

1. `mother_bank/MANIFEST.json`
2. `references/factors_lab_contract.md`
3. `references/dedup_policy.md`
4. `references/pitfalls.md`
5. `references/playbook.md`
6. `references/output_schema.md`

如果用户要求调用 PandaAI，再额外读取 `references/pandaai_online.md`。

不要使用原 PandaAI 字段表或算子表扩展搜索空间。仓库里没有这些旧表，是有意删除的。

## 3. 字段与算子：硬约束

候选的 `canonical_expression` 必须完全符合当前 factors_lab AST。

- 字段只能来自 `references/factors_lab_contract.md` 中的 `Allowed numeric features`；
- `group_neutralize.group` 只能使用 contract 中允许的分组字段；
- AST kind、operator、window、parameter 规则必须遵循 contract；
- feature lag 必须为非负整数；
- 禁止任何 `future_*`、forward return、label、target 等未来标签进入候选；
- 不得发明 `BIAS`、`ROC`、`RSI`、`KDJ` 等母库 AST 中不存在的“宏名称”。如果该思想能用已有 AST 表达，就必须展开成已有节点；不能表达就放弃该候选。

## 4. 因子生成原则

优先从不同经济机制产生候选：

- 反转 / 动量 / 趋势持续；
- 波动、尾部风险、偏度；
- 量价确认与价格冲击；
- 流动性与换手结构；
- 价值；
- 盈利能力与盈利质量；
- 现金流质量；
- 杠杆、资本结构；
- 成长与投资；
- 行业中性后的相对信号；
- 多机制组合，但必须能解释每一项为什么同时存在。

不要为了达到候选数量而做：

- 同一公式只把 20 日换成 21/22/30 日；
- 同一信号只取负号、倒数、log、rank、zscore 再当新因子；
- 同一表达式乘 10、加 1、除以正常数再当新因子；
- 同一正值比率的正比/倒数同时出现；
- 只把 lower-is-better 改成 higher-is-better 来伪装新因子。

方向 `0/1` 是交易解释元数据，不参与“是否是同一个底层排序暴露”的判定。

## 5. 强制去重

每一批候选在展示给用户前都必须通过：

```bash
python scripts/validate_candidates.py \
  --input candidate_batch.json \
  --output accepted_candidates.json \
  --report audit_report.json
```

如果 validator 拒绝候选：

- 不得把它仍然列为有效候选；
- 不得仅改名字或方向后再次提交；
- 对 `EXACT_DUPLICATE` 或 `RANK_EQUIVALENT_DUPLICATE`，必须换机制；
- 对 `PARAMETER_ONLY_VARIANT`，默认保留该批中第一个，其余换机制；
- 对 `UNSUPPORTED_FEATURE/OPERATOR`，不得自行扩充 contract；
- 对 `ZERO_MASK_CONDITIONAL`，优先重构表达式，而不是把 0 换成极小数等规避检查。

## 6. 之前已经暴露出来的重复陷阱

以下类型必须主动识别：

- `ABS(OPEN / DELAY(CLOSE,1))` 与 `OPEN / DELAY(CLOSE,1)`：价格比率已为正，ABS 冗余；
- `SUM(condition,N)/N` 与 `MEAN(condition,N)`：完全相同；
- `x` 与 `log(x)`（当 x 可证明为正）：排序等价；
- `x` 与 `a*x+b`（a>0）：排序等价；
- `x` 与 `-x` / `a*x+b`（a<0）：反向排序等价；
- `x/y` 与 `y/x`（x、y 均可证明为正）：反向排序等价；
- `close/MA(close,N)-1` 与 `MA(close,N)/close`：正值比率的单调倒数，本质是同一暴露的反向；
- `rank(x)`、`zscore(x)` 与 x：作为横截面排序信号时不得算成独立新因子。

Validator 会覆盖其中的可静态证明情形；AI 仍需做经济语义层去重。

## 7. 条件因子规则

默认禁止：

```text
IF(condition, signal, 0)
IF(condition, 0, signal)
```

原因是大量条件不满足股票会同时得到 0，在横截面排序中形成巨大并列质量点。除非用户明确要求研究这种 gate，并说明 0 的经济含义，否则不要使用。

## 8. 数值稳健性

对任何除法都先问：分母是否可能为 0 或接近 0？

- 价格、正市值等可证明为正的分母风险较低；
- 收益、利润、税前利润、现金流、斜率、差值等不能假定远离 0；
- 不要随意加 `1e-6` 就宣称问题解决，因为不同量纲下该常数含义不同；
- 对财务存量与流量不要混淆 TTM：资产、负债、权益是时点量；收入、利润、现金流等才适合滚动四季累计。

## 9. 候选数量与多重检验

候选越多，偶然胜出的概率越高。每批先提出机制不同的候选，再执行验证。

推荐：

- 第一轮 10–30 个机制明显不同的候选；
- 不要一次生成数百个轻微变体；
- 记录所有真正测试过的候选，包括失败者；
- PandaAI 或 factors_lab 回测结果都不能反过来修改历史试验数。

## 10. PandaAI 在线验证（可选）

只有用户要求在线测试时才做。

先验证 factors_lab 兼容性，再执行：

```bash
python scripts/export_pandaai_manifest.py \
  --input accepted_candidates.json \
  --output pandaai_candidates.txt \
  --report pandaai_export_report.json
```

只有可无损转换到 PandaAI 安全子集的候选才会进入 manifest。不能转换的候选仍是合法 factors_lab 候选，不要为了迁就 PandaAI 改写其经济含义。

然后可复用：

```bash
python scripts/batch.py pandaai_candidates.txt ...
```

登录由用户自己执行 `pandaai-cli login`。绝不索取、打印或保存用户手机号、密码、token 或配置文件内容。

## 11. 输出规则

候选原始输出必须符合 `references/output_schema.md`，其中：

- `canonical_expression` 是唯一权威公式；
- `normalized_formula` 只是人类可读形式；
- `direction=1` 表示 higher is better；`direction=0` 表示 lower is better；
- `hypothesis` 必须用一句话说明机制；
- `family` 必须标明因子族；
- 不要提前分配 factors_lab 的 16 位正式 `factor_id`。

正式 ID 应由 factors_lab 导入流程按母库当前 `next_factor_id` 分配，避免并发冲突。

## 12. 质量优先级

依次优先：

1. 无未来信息；
2. factors_lab 可执行；
3. 与母库非重复；
4. 数值稳健；
5. 经济机制清楚；
6. 与已有候选保持机制多样性；
7. PandaAI 在线表现（若测试）；
8. factors_lab 本地正式表现。

任何在线回测都只是历史诊断，不构成投资建议。
