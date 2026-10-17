# Problems Faced Log

> Maintained by the AI agent (and by me). Add an entry for every real problem hit during development:
> bugs, failing tests, wrong assumptions, design changes, environment issues, and surprising results.
> This file is also my interview material: "Tell me about a challenge you faced in this project."
> Newest entries at the TOP. Keep entries short and concrete.

## Entry template (copy for each problem)
```
### P-000 | [short title]
- Date:
- Phase:
- Status: Open / Resolved / Workaround
- What happened: (symptom, error message, or unexpected result)
- Root cause: (why it really happened)
- How it was fixed: (what changed, which files)
- Alternatives considered:
- Lesson learned:
- Related doc updated: (yes/no, which file)
```

---

## Log

### P-002 | Slow generation due to iterative row updates in anomaly injection
- Date: 2026-10-17
- Phase: 1
- Status: Resolved
- What happened: The initial anomaly injection implementation used Python dictionary and row iteration with `.at[idx, ...]`, resulting in slow performance (~13s during unit tests).
- Root cause: Repeated scalar `.at` or `.loc` assignments in pandas incur large overhead across hundreds of rows.
- How it was fixed: Fully vectorized anomaly injections in `scripts/generate_synthetic_ledger.py` using NumPy index slicing and array assignments. 50,000 rows now generate in ~0.28s.
- Alternatives considered: Retaining row iteration for logic simplicity, rejected because AUDIT_RULES.md and CODE_STYLE.md mandate vectorized pandas operations.
- Lesson learned: Always apply vectorized operations across slices in pandas/NumPy to ensure sub-second dataset generation.
- Related doc updated: no

### P-001 | Flawed test assertion assuming disjoint transaction IDs between clean and anomalous ledgers
- Date: 2026-10-17
- Phase: 1
- Status: Resolved
- What happened: `test_synthetic_ledger_clean_has_no_injected_anomalies` failed with `assert len(gt_txns.intersection(clean_txns)) == 0 (30 == 0)`.
- Root cause: The test assumed `ledger_clean.csv` and `ground_truth.csv` had disjoint transaction IDs. In reality, `ledger.csv` is derived from `ledger_clean.csv`, sharing the baseline IDs (`TXN-000001` to `TXN-050000`).
- How it was fixed: Updated the test in `tests/unit/test_synthetic_ledger.py` to assert the true invariant: all transactions in `ledger_clean` (including those corresponding to ground truth entries in `ledger.csv`) violate none of the audit rules and satisfy all clean criteria.
- Alternatives considered: Prefixing clean IDs with `TXN-CLN-`, rejected because keeping 1-to-1 ID alignment allows direct row-level comparison between baseline and corrupted transactions.
- Lesson learned: Unit test assertions should validate business domain invariants rather than superficial structural assumptions.
- Related doc updated: no

