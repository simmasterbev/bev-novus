# Bev Novus 2.0 roadmap and test gates

2.0 is an evidence release: a criterion can fail while the release still ships, but the failure and its controls must remain visible.

## Gates

| Area | Test | 2.0 gate |
|---|---|---|
| Accounting | Matter drift across fixed-seed runs | `< 1e-8` per 1,000 steps |
| Replication | Independent seeded runs | At least 10 retained runs |
| Persistence | Pattern lifetime and coexistence | Report median lifetime and extinction rate; no visual-only pass |
| Repair | Damage versus matched no-metabolism control | Report recovery ratio and control difference |
| Lineage | Birth parent/child records | Every birth has an ID, parent estimate, genotype snapshot, and viability outcome |
| Heredity | Parent-child versus shuffled-parent similarity | Positive correlation required for a heredity pass |
| Ecology | Spatial versus well-mixed comparison | Report coexistence, patchiness, and interaction differences |
| Evolvability | Viable novelty under matched mutation budgets | Novelty must persist beyond the initial transient |
| Open-endedness | Long-run continuing innovation | Never marked passed without multi-metric, ablation-backed evidence |

## Release sequence

- v1.2: parameter sweeps and coexistence search.
- v1.3: individuality, boundary stability, and repair.
- v1.4: explicit lineage graph and event logs.
- v1.5: heredity and selection controls.
- v1.6: resource niches and interaction network.
- v1.7: group persistence and collective tests.
- v1.8: evolvability replay experiments.
- v2.0: replicated audit report, dashboard, controls, and public release.

The current world has model-internal seed emission, resource recycling, repair probes, and inherited traits. It does not yet have enough evidence to claim sustained open-ended evolution; the audit makes that uncertainty part of the product.
