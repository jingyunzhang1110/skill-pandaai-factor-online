# Factor generation playbook

## Step 1 — define the campaign

State candidate count, target families, rebalance horizon, exclusions and whether PandaAI online diagnostics will be used.

## Step 2 — inspect the mother bank

Search the 549-factor snapshot for the intended mechanism, not just the exact name. If the bank already contains the same ordering exposure, choose another mechanism.

## Step 3 — propose mechanisms before formulas

For each candidate write one sentence answering: what market behavior should make this signal predictive, and why should the direction be positive or negative?

## Step 4 — translate into factors_lab AST

Use only the current contract. Prefer simple expressions. Add normalization only when it changes the economic meaning or controls a real scale problem.

## Step 5 — diversify

A good batch spans multiple families. Avoid filling a batch with many versions of one momentum or valuation idea.

## Step 6 — static audit

Run `validate_candidates.py`. Replace rejected candidates with new mechanisms rather than cosmetic rewrites.

## Step 7 — optional PandaAI screen

Export only the losslessly translatable subset. Use PandaAI results as diagnostics, not as the final acceptance standard. Preserve all attempted candidates in the experiment ledger.

## Step 8 — local formal evaluation

Candidates that survive the source-stage screen still need the normal factors_lab single-factor evaluation, deduplication and multi-factor workflow.
