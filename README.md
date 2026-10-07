# factors_lab 因子挖掘 Skill

这是一个独立的 A 股因子挖掘 Skill。它与 `factors_lab` 不存在运行时依赖，只共享统一的 JSON 与 canonical AST 标准。

Skill 负责：

1. 根据经济/市场机制提出新因子；
2. 只使用规定字段和算子构造 canonical AST；
3. 用 Skill 自己的 `mother_bank/` 参考库做静态去重；
4. 输出可直接交给 factors_lab `import-factors` 的 JSON。

## 本地参考库

```text
mother_bank/
├─ clean_seed_factor_bank.json   # 初始549个
├─ added_xxx.json                # 用户以后手工加入
└─ MANIFEST.json
```

validator 会自动读取这个目录里除 `MANIFEST.json` 外的全部 JSON。

以后如果你希望 Skill 不再重复生成某批新因子，把验证后的 `ready_for_factors_lab.json` 复制一份到 `mother_bank/`，使用唯一文件名保存即可。

完整的人类操作说明：

`HUMAN_GUIDE.zh-CN.md`

## 生成与验证

按 `examples/new_factor_batch.example.json` 生成，然后：

```bash
python scripts/validate_candidates.py \
  --input generated_batch.json \
  --output ready_for_factors_lab.json \
  --report audit_report.json
```

通过后的 `ready_for_factors_lab.json` 可以手工复制到 factors_lab，再由 factors_lab 自己完成 RAW 判重、ID、Registry、单因子和多因子流程。

## 目录

```text
SKILL.md
SKILL.zh-CN.md
HUMAN_GUIDE.zh-CN.md
mother_bank/
  clean_seed_factor_bank.json
  MANIFEST.json
references/
  factors_lab_contract.md
  output_schema.md
  dedup_policy.md
  pitfalls.md
  playbook.md
scripts/
  validate_candidates.py
  bootstrap.py
  selftest.py
tests/
  test_validate_candidates.py
examples/
  new_factor_batch.example.json
```
