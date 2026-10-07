# 给人类用户的说明：如何维护 Skill 的参考因子库

这个 Skill 和 factors_lab 是两个完全独立的项目。

**不要让 Skill 去读取 factors_lab 的目录，也不要建立自动同步。**  
你只需要在希望 Skill “记住”某批因子、以后避免再次生成时，手工把那批因子的 JSON 放进 Skill 自己的 `mother_bank/` 目录。

## 应该放到哪里

路径就是：

```text
skill-pandaai-factor-online/
└─ mother_bank/
```

初始 549 个因子已经在：

```text
mother_bank/clean_seed_factor_bank.json
```

以后新增的参考因子与它放在**同一级目录**，例如：

```text
mother_bank/
├─ clean_seed_factor_bank.json   # 初始549个，保留，不覆盖
├─ added_20261007_001.json       # 以后新增
├─ added_20261012_001.json
├─ added_20261103_001.json
└─ MANIFEST.json
```

## 推荐放什么文件

最推荐放 Skill 自己最终生成的：

```text
ready_for_factors_lab.json
```

在把它保存进 `mother_bank/` 时，为了不覆盖旧文件，改一个唯一文件名即可，例如：

```text
ready_for_factors_lab.json
        ↓ 复制并改名
mother_bank/added_20261007_001.json
```

文件内容**不要改**。它本来就是：

```json
{
  "schema_version": 1,
  "batch_name": "...",
  "source": "...",
  "records": [
    {
      "source_record_id": "...",
      "name": "...",
      "canonical_expression": {}
    }
  ]
}
```

validator 能直接读取这种 `records` 格式。

## 什么时候放进去

当你认为某批因子以后应该被 Skill 当作“已经见过的因子”时，就放进去。

通常最合适的是：

1. Skill 生成并验证 `ready_for_factors_lab.json`；
2. 你把它送进 factors_lab；
3. 确认这批因子已经进入你的研究流程；
4. 再复制一份到 Skill 的 `mother_bank/`。

这样下次再挖因子时，Skill 会同时参考：

```text
初始549个
+
你后来手工放进 mother_bank/ 的所有因子
```

从而减少重复生成。

## validator 如何读取

默认执行：

```bash
python scripts/validate_candidates.py \
  --input generated_batch.json \
  --output ready_for_factors_lab.json \
  --report audit_report.json
```

时，不需要额外参数。

程序会自动扫描：

```text
mother_bank/*.json
```

并忽略：

```text
mother_bank/MANIFEST.json
```

支持两种参考文件：

- 初始快照的 `factors: [...]` 格式；
- 新链路的 `records: [...]` 格式。

只要其中的记录包含合法 `canonical_expression`，就会参与 exact / rank-equivalent 去重。

## 不要放什么

不要把下面这些文件放进 `mother_bank/`：

- `audit_report.json`；
- 日志；
- 回测结果；
- CSV；
- 临时 JSON；
- 不含 `factors` 或 `records` 的其他 JSON。

也不要覆盖：

```text
mother_bank/clean_seed_factor_bank.json
```

它是初始 549 因子的固定参考快照。

## 最重要的一点

```text
Skill 的 mother_bank/
≠
factors_lab 的 RAW
```

它只是 Skill 自己的“参考书架”。

两个项目之间唯一需要保持一致的是**JSON/AST 标准**。新因子的传递由你通过文件手工完成，不存在自动同步、自动刷新或跨项目路径依赖。
