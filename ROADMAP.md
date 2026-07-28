# Bev Novus roadmap

## Artificial chemistry to an open-ended evolution research platform

Bev Novus is a small physical universe for studying what can emerge from local interactions. The project should create richer physics, chemistry, and ecology instead of hand-designing organisms.

Every feature must be:

- local and mechanically explainable;
- objectively measurable;
- reproducible from a seed and parameter set;
- inspectable in the viewer and experiment archive;
- compared against an ablation or control when it makes a scientific claim.

## Phase 0 - Foundation (current)

Implemented foundations:

- conserved matter, resource and waste fields;
- recycling, regrowth, dormancy, and seed emission;
- mutation and inherited traits;
- connected-component pattern census and lineage records;
- configurable viewer, CPU/GPU engines, batch sweeps, replay, export, and GUI preflight checks.

The foundation is a respectable artificial-chemistry substrate, but it is not evidence of open-ended evolution.

## Phase 1 - Better physics

Goal: introduce simple force-bearing body matter without replacing the existing world until the mechanics are validated.

### 1.1 Force system

Tasks:

- add a force accumulator;
- use spatial bins/cell lists for local neighbor lookup;
- add short-range repulsion and medium-range attraction kernels;
- add configurable interaction radius, strength, drag, and mobility;
- preserve periodic-boundary behavior and matter accounting.

Acceptance: isolated bodies remain finite, do not collapse into one point, and show stable cohesion across fixed seeds.

### 1.2 Overdamped particle motion

Use `velocity = mobility * force` and `position += velocity * dt` before considering momentum or rigid-body physics.

Tasks:

- particle position, velocity, mass, and drag;
- timestep and stability sweep;
- numerical-fault detection;
- body/resource/waste coupling tests.

Acceptance: bodies deform and translate smoothly, mass drift remains within the existing accounting gate, and the force model is faster than an O(N²) implementation at comparable particle counts.

### 1.3 Hybrid world

Keep resource and waste as grid fields while representing body matter experimentally as particles. Maintain a field-only control so any benefit from mechanics is measurable.

Acceptance: particle and field controls can run from the same seed/configuration and report comparable persistence, resource intake, reproduction, and morphology metrics.

## Phase 2 - Internal complexity

### 2.1 Internal state

Add optional per-particle state for energy, signal, affinity, age, stress, dormancy, repair, and mutability. Keep each state bounded, conserved where appropriate, and logged.

Acceptance: state updates remain finite and ablations show that each claimed state affects the intended observable.

### 2.2 Heritable trait expansion

Expand continuous inherited traits gradually:

- attraction and repulsion preference;
- mobility and drag;
- metabolism and repair;
- dormancy tendency;
- signal strength;
- reproduction threshold;
- resource preference.

Do not evolve force kernels yet. First establish that the fixed kernels are meaningful.

Acceptance: parent-child similarity exceeds shuffled-parent controls and inherited differences predict survival, intake, repair, or reproduction.

### 2.3 Local signaling

Add generic local signals that diffuse through neighboring cells or particles. Signals may support recruitment, repair, colony formation, and coordinated reproduction without naming those behaviors as rules.

Acceptance: signaling produces measurable changes under signal-on versus signal-off controls, with no hidden global state.

## Phase 3 - Real ecology

### 3.1 Environmental heterogeneity

Add optional temperature, toxicity, seasonal cycles, and local disasters.

Acceptance: environments produce distinct, reproducible selective pressures and spatial structure changes coexistence relative to well-mixed controls.

### 3.2 Generic chemical fields

Add optional pheromone, catalyst, inhibitor, and attractant fields. These remain generic chemical channels, not named food, brain, or organism systems.

Acceptance: fields have explicit diffusion/decay/source rules, exportable parameters, and ablations.

### 3.3 Niche formation

Measure strategies from behavior rather than labels: recycling, dormancy, aggressive growth, exploration, resource specialization, and facilitation.

Acceptance: strategy clusters replicate across seeds and occupy measurably different environmental regimes.

## Phase 4 - Evolution

### 4.1 Better heredity

Track continuous genomes, independent parent mutations, mutation spectra, inheritance, divergence, and genotype snapshots.

### 4.2 Long-term lineages

Generate durable lineage trees and measure branching, extinction, persistence, diversity, and generation depth.

### 4.3 Ecological selection

Avoid an explicit fitness bonus. Let selection emerge from survival, reproduction, resource efficiency, repair, robustness, and interactions.

Acceptance: selection effects survive mutation-off, neutral-trait, shuffled-parent, and matched-budget controls.

## Phase 5 - Instrumentation

This phase is a prerequisite for strong claims in later phases.

### 5.1 Experiment database

Persist seed, full parameters, code/version, metrics, snapshots, events, traits, and lineage records.

### 5.2 Event detection

Bookmark first reproduction, extinction, first colony, mutation burst, longest lineage, highest complexity, largest body, and major ecological transitions.

### 5.3 Analysis dashboard

Plot diversity, entropy, persistence, body count, resource, waste, mutation, lineage count, novelty, niches, and control differences.

### 5.4 Morphology statistics

Add compactness, branching, symmetry, holes, perimeter, density, and optionally fractal dimension. Keep heuristic labels explicitly separate from organism claims.

Acceptance: a run can be independently replayed from its archive and produce the same event/metric record within documented numerical tolerance.

## Phase 6 - Massive search

### 6.1 Experiment runner

Scale from thousands toward 10,000, 50,000, and 100,000 reproducible simulations using parallel CPU/GPU screening and deterministic replay.

### 6.2 Ranking

Rank by persistence, diversity, novelty, reproduction, complexity, ecological richness, and robustness rather than a single saturated score.

### 6.3 World archive

Store parameters, metrics, frames, lineages, traits, and provenance for retained worlds.

### 6.4 Similarity search

Support closest worlds, most unique worlds, largest deviations, and cluster members using metric vectors and morphology/ecology signatures.

Acceptance: a batch can be stopped, resumed, audited, and re-ranked without rerunning completed worlds.

## Phase 7 - Multiverse analysis

Only begin after the force model, instrumentation, and large-scale archive are stable.

### 7.1 World space

Represent each simulation as a point based on morphology, ecology, lineage, and diversity.

### 7.2 Embedding

Explore 3D/4D embeddings of world populations and identify clusters, outliers, and transitions.

### 7.3 Layered universes

Experiment with resource leakage, migrating seeds, chemical leakage, and cross-world inheritance.

### 7.4 Dynamic universe graph

Connect worlds by measured similarity or controlled migration rather than fixed adjacency.

Acceptance: multiverse results preserve provenance and can be reproduced from the underlying world archives.

## Phase 8 - Research platform

Deliver experiment presets, batch comparison, parameter sweeps, statistical summaries, paper-quality plots, reproducibility tools, dataset export, and an interactive lineage browser.

Stretch goals:

- continuous space;
- compute-shader particle simulation;
- 3D physics;
- evolution of interaction kernels;
- mutating chemical reactions.

## Existing 2.0 evidence gates

These gates remain active during the expanded roadmap:

| Area | Test | Gate |
|---|---|---|
| Accounting | Matter drift across fixed-seed runs | `< 1e-8` per 1,000 steps |
| Replication | Independent seeded runs | At least 10 retained runs |
| Persistence | Pattern lifetime/coexistence | Report median lifetime and extinction rate |
| Repair | Damage versus no-metabolism control | Report recovery and control difference |
| Lineage | Birth parent/child records | Every birth has IDs, genotype, and viability outcome |
| Heredity | Parent-child versus shuffled-parent similarity | Positive correlation required |
| Ecology | Spatial versus well-mixed comparison | Report coexistence, patchiness, interactions |
| Evolvability | Novelty under matched mutation budgets | Novelty must persist beyond transients |
| Open-endedness | Long-run continuing innovation | Never pass without multi-metric ablation evidence |

## Immediate execution order

1. Freeze the current field-only engine as the control baseline.
2. Build an isolated overdamped particle prototype with spatial binning.
3. Validate repulsion, cohesion, drag, boundaries, and numerical stability.
4. Couple particles to existing resource and waste grids.
5. Add side-by-side field/particle visualization and metrics.
6. Only after the hybrid control is stable, add internal states and new heritable traits.
7. Expand instrumentation before starting 100,000-run searches.

## Definition of success

Success is not identifying a programmed organism. It is running large reproducible experiment populations, observing distinct heritable ecological strategies under different conditions, quantifying them rigorously, and allowing the evidence—not the implementation—to determine whether increasingly open-ended behavior is present.
