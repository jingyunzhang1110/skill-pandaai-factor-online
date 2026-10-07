# factors_lab 因子挖掘 Skill

这是一个面向 `jingyunzhang1110/factors_lab` 的纯因子挖掘 Skill。它现在直接输出 **factors_lab 新版 `import-factors` 可以读取的 JSON**，不再使用旧的 candidate/factors 中间格式。

核心保证：

1. 只使用固定白名单中的 factors_lab 字段；
2. 只使用当前 canonical AST 已实现的 kind/operator/参数；
3. 禁止未来信息、负 lag、非法窗口和未定义 AST key；
4. 检查 AST 节点数、深度、lookback 和已知量纲冲突；
5. 与 549 初始母库做 exact / rank-equivalent 去重，并做批内去重；
6. 默认淘汰 parameter-only 变体和 zero-mask conditional；
7. Skill 不分配正式 16 位 `factor_id`；
8. 最终 JSON 可直接进入 factors_lab append-only RAW 导入链。

## 直接接口

按：

`examples/new_factor_batch.example.json`

生成批次，然后运行：

```bash
python scripts/validate_candidates.py \
  --input generated_batch.json \
  --output ready_for_factors_lab.json \
  --report audit_report.json
```

通过后，把 `ready_for_factors_lab.json` 放入 factors_lab，直接执行：

```powershell
python .\common_factor\top.py import-factors .\ready_for_factors_lab.json
```

后续由 factors_lab 自动完成：

```text
AST canonicalize / fingerprint / 历史判重 / ID分配
→ 新 RAW 分片
→ factors.sqlite
→ single_factor
→ multi_factor
```

完整规则请读 `SKILL.zh-CN.md`、`references/factors_lab_contract.md` 和 `references/output_schema.md`。

## 目录

```text
SKILL.md
SKILL.zh-CN.md
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
  refresh_mother_bank.py
  bootstrap.py
  selftest.py
tests/
  test_validate_candidates.py
examples/
  new_factor_batch.example.json
```

`mother_bank/clean_seed_factor_bank.json` 只是 Skill 内部用于静态去重的“唯一因子快照”，不是 factors_lab 运行时的 clean 文件。factors_lab 当前运行时直接从 append-only RAW 分片 bootstrap 到 `factors.sqlite`。
