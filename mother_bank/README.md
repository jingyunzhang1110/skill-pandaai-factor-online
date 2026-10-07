# mother_bank：Skill 本地参考因子目录

这个目录只属于本 Skill，用于在生成新因子前做静态重复检查。

它与 factors_lab 的 RAW、SQLite、单因子或多因子目录没有任何运行时连接。

## 初始参考库

`clean_seed_factor_bank.json` 是固定的初始 549 因子唯一快照。

不要覆盖或删除它。

## 后续参考因子

人类用户可以把后续已经生成、希望 Skill 以后避免重复的因子 JSON 直接放在本目录，例如：

```text
mother_bank/
├─ clean_seed_factor_bank.json
├─ added_20261007_001.json
├─ added_20261012_001.json
└─ MANIFEST.json
```

推荐直接复制 Skill 验证后的 `ready_for_factors_lab.json`，只改文件名，不改内容。

validator 默认自动扫描本目录全部 `*.json`，但忽略 `MANIFEST.json`。它同时支持：

- `factors: [...]` 的初始快照格式；
- `records: [...]` 的新版直接导入格式。

含合法 `canonical_expression` 的记录都会参与去重。

详细的人类操作说明见根目录 `HUMAN_GUIDE.zh-CN.md`。
