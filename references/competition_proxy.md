# 比赛规则代理：离线输入与使用

仅在用户明确选择“比赛准备模式”后使用。先完成常规挖掘、成本复盘和候选登记；本工具不调用 CLI、不创建因子、不提交因子池。

## 输入快照

从完成的 `factor_result` 保存每个候选的 RankIC 序列，以及按月整理的多头端组合数据。快照必须是 UTF-8 JSON：

```json
{
  "as_of": "2026-07-31",
  "factors": [{
    "name": "F-A17",
    "effective_date": "2026-01-10",
    "rank_ic": [
      {"date": "2026-01-08", "value": 0.031, "sample_type": "in_sample"},
      {"date": "2026-01-15", "value": 0.014, "sample_type": "out_of_sample"}
    ],
    "portfolio_months": [{
      "month": "2026-07",
      "excess_month": 0.012,
      "daily_excess_returns": [0.002, -0.001, 0.003],
      "turnover": 0.18,
      "max_drawdown": 0.04
    }]
  }]
}
```

- `rank_ic` 来自 `query_rank_ic_sequence_chart`；同月多期记录由脚本做简单均值聚合。
- `sample_type: out_of_sample` 只标记正式生效后新增的真实记录。没有它时，A 仅按近五年代理，脚本会发出警告。
- `turnover`、`excess_month`、`max_drawdown` 使用小数：`0.18` 表示 18%。C 的 `BaseTurn` 固定为 `0.3`（30%）。
- `daily_excess_returns` 是该月全部日频超额收益；少于两个值的月份不能计算 Sharpe，脚本会跳过并报告。

## 运行

```bash
python3 scripts/competition_proxy.py competition-snapshot.json
```

输出的 `official_score` 永远是 `false`：

- `A_proxy` 用近五年加已标记 OOS 的月度 RankIC 计算代理；
- `B_proxy` 只有在 `effective_date` 后存在真实记录时才可用；
- `C_proxy` 是输入组合账本的月度代理，单因子 CLI 结果不能替代平台池级等权合成组合。

保存原始 `factor_result` JSON、生成的快照和候选登记表。它们是可复核的研究记录，不是官方积分或未来收益预测。
