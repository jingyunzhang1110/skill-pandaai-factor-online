# Mother bank snapshot

`clean_seed_factor_bank.json` in this Skill is **not** a factors_lab runtime file.

It is a local, unique-factor snapshot used only for static duplicate detection while mining. The current snapshot represents the initial factors_lab mother bank:

- 549 unique Factor IDs;
- 836 historical source records behind those IDs;
- next ID at that point: `0000000000000550`.

factors_lab itself now uses:

```text
common_factor/catalog/raw/*.json
→ bootstrap
→ factors.sqlite
```

and does not maintain `clean_seed_factor_bank.json`.

Before a later mining campaign, refresh this Skill's dedup snapshot from a local factors_lab checkout:

```bash
python scripts/refresh_mother_bank.py \
  --source <factors_lab>/common_factor/catalog/raw \
  --source-commit <current-factors_lab-commit>
```

The refresh script merges all RAW shards by Factor ID. If an old initial RAW record lacks a canonical AST, the existing Skill snapshot is used only to preserve that already-resolved AST. Newly imported factors already carry canonical AST in their RAW shard.
