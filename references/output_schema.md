# factors_lab 新因子导入 JSON 规范

Skill 的输入草稿和最终输出都使用 factors_lab `common_factor import-factors` 的同一 schema。

## 顶层

只能有 4 个字段：

```json
{
  "schema_version": 1,
  "batch_name": "fm_20261007_001",
  "source": "factor-mining-skill",
  "records": []
}
```

- `schema_version`：固定为 1。
- `batch_name`：非空且每批唯一。已导入的 batch_name 不得复用给另一批内容。
- `source`：本批总体来源。
- `records`：非空数组。

禁止增加 `factor_id`、`next_factor_id`、fingerprint 等身份字段。

## 每条 record

只允许：

```json
{
  "source_record_id": "FM-20261007-001-0001",
  "name": "20日相对250日换手率",
  "source": "factor-mining-skill",
  "source_ref": "LLM factor mining batch fm_20261007_001",
  "formula_provenance": "由经济假设直接构造并翻译为 factors_lab canonical AST",
  "original_formula": "MA(turnover,20) / MA(turnover,250)",
  "economic_rationale": "近期换手率相对长期换手率抬升，刻画交易关注度和活跃度的变化。",
  "source_constraints": "分母为长期平均换手率；极低换手股票可能产生数值放大。",
  "canonical_expression": {}
}
```

字段要求：

- `source_record_id`：必填、批内唯一，并尽量全局唯一。
- `name`：必填，且为避免冗长日志/报告与不可读命名，未来新挖候选长度不得超过 40 个字符；名称只概括核心机制与关键输入。
- `source`：建议填写；缺省时可继承顶层 source，但 Skill 最终输出会补齐。
- `source_ref`：来源定位。LLM 自研因子应写明批次/机制，不得伪造论文或研报页码。
- `formula_provenance`：说明公式是原文抄录、原文形式化还是 LLM 新假设。
- `original_formula`：必填的人类可读公式。
- `economic_rationale`：必填，解释为什么可能产生横截面收益差异。
- `source_constraints`：记录适用条件、数值风险、PIT 限制等；没有特殊限制可写空字符串。
- `canonical_expression`：必填；完整规范见 `factors_lab_contract.md`。

## 明确禁止的 record 字段

LLM 不得输出：

```text
factor_id
expression_fingerprint
duplicate_type
representation
parse_error
import_batch
```

这些由 factors_lab 的导入器根据全部历史 RAW 统一生成/管理。

## 验证与交付

```bash
python scripts/validate_candidates.py \
  --input generated_batch.json \
  --output ready_for_factors_lab.json \
  --report audit_report.json
```

`ready_for_factors_lab.json` 仍然是上面的同一 schema，可以直接复制到 factors_lab 后执行：

```powershell
python .\common_factor\top.py import-factors .\ready_for_factors_lab.json
```
