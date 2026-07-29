# Bev Novus roadmap

> Evidence-gated path from an artificial chemistry and particle-physics laboratory toward a defensible study of evolving individuals. Updated 2026-07-29. A completed engineering feature is not automatically a completed scientific milestone.

## North star

Bev Novus should eventually let us test a demanding question: can localized forms arise from local rules, maintain themselves using environmental resources, reproduce with inherited variation, diversify in an ecology, and continue generating viable novelty?

The order matters. We should not call a pattern alive because it looks compelling, and we should not add extra rules to a world that has not first shown reliable persistence and accounting.

## Current state

| Area | Current status | What it does not establish |
| --- | --- | --- |
| Field world | Instrumented 2D body/resource/waste world with seed emission, trait/mutability fields, lineage records, controls, and audit metrics. | The retained v2 audit did not pass persistence or evolvability at its 1,000-step horizon. |
| Particle hybrid | Particle bodies coupled to resource/waste grids, with cohesion, repulsion, drag, taxis, periodic boundaries, GPU batching, and particle persistence metrics. | It has no particle reproduction, lineage, or particle trait inheritance. Zero particle births are expected, not a failure signal. |
| Operations | Browser viewer, local GUI, GPU screening, CPU/reference paths, snapshots, JSON reports, adaptive parameter scheduling, and audit pages. | Search throughput does not prove a biological result. |

The tracked `v2-audit.json` remains the reference for the original field audit: accounting and 10-seed replication passed; persistence and evolvability failed; collective individuality and open-endedness were not demonstrated.

## Research standard

Every claim needs four things:

1. a measurable definition;
2. fixed seeds and saved parameters sufficient to replay it;
3. a relevant control or ablation;
4. a result that holds across independent runs rather than one attractive frame.

Heuristic morphology labels such as *seedlet*, *cluster*, or *colony* remain observation aids. They are never organism labels by themselves.

## Workstream A - particle individuality baseline

**Question:** Can a particle body be a bounded, resource-supported, persistent physical individual before we ask it to reproduce?

### A1. Fix a small canonical panel

Select a small number of particle parameter sets from existing campaigns. Preserve the full configuration, seed, engine version, resolution, step rate, and snapshot cadence.

**Pass gate:** each retained condition can be replayed and yields finite state plus accounting drift within its documented tolerance.

### A2. Measure persistence, not just survival count

For each canonical condition, record body mass, live particles, connectedness/compactness, resource exposure, waste exposure, extinction time, and time-resolved accounting.

Run matched no-resource, no-metabolism, no-recycling, and well-mixed/spatial controls where applicable.

**Pass gate:** a spatial, resource-coupled condition has materially longer persistence or better boundedness than its matched controls across multiple seeds.

### A3. Damage and recovery

At predefined times, remove a fixed fraction of a localized body, then compare recovered mass, compactness, and boundary score with an undamaged replay and a no-metabolism control.

**Pass gate:** recovery reaches a declared fraction of the pre-damage score within a declared horizon, and the advantage weakens or vanishes without metabolism/resource coupling.

### A4. Decide honestly

If A2/A3 do not pass, simplify or repair the particle physical substrate. Do not add reproduction, signals, or extra chemistry merely to decorate an unstable body.

## Workstream B - explicit particle reproduction and heredity

**Entry condition:** Workstream A has shown a repeatable, controlled persistence/repair advantage.

### B1. Implement a conservative division mechanism

Division must transfer existing parent particle mass to an offset daughter; it must not create a new body from nowhere. Record parent ID, child ID, time, transferred mass, and post-division viability.

### B2. Add an inherited description

Begin with a small, bounded heritable vector controlling physical or metabolic parameters. Mutation must be explicit, bounded, and logged. Development must map that vector to a particle body reproducibly.

### B3. Test heredity and selection

Compare parent-child similarity with shuffled-parent and mutation-off controls. Test whether inherited differences predict survival, resource intake, repair, or reproduction rather than simply correlating with a transient parameter sweep.

**Pass gate:** every particle birth is traceable; parent-child similarity exceeds shuffled controls; an inherited difference predicts at least one fitness-relevant outcome under controls.

## Workstream C - ecology before complexity for its own sake

**Question:** Do different persistent/reproducing strategies occupy different resource situations?

1. Add a second resource regime only after B is instrumented.
2. Measure competition, waste interference, facilitation, mergers, and spatial occupancy.
3. Compare spatial and well-mixed versions using the same seeds and average supply.
4. Preserve both coexistence and collapse examples.

**Pass gate:** trait groups occupy distinguishable regimes for a declared long horizon, and removing spatial structure measurably reduces coexistence or niche separation.

## Workstream D - higher-level individuality and evolvability

### D1. Collective individuality

Track multi-core aggregates and compare them with the same members separated. Require persistence, group identity through reproduction, and performance benefit rather than mere contact.

### D2. Evolvability

Vary behavior, mutability, and developmental mapping independently. Replay ancestors and descendants under matched mutation budgets.

**Pass gate:** descendants generate more viable, measurable novelty than ancestors without merely raising mutation rate or exploiting an unaccounted external source.

## Workstream E - open-endedness audit

Open-endedness is an audit result, not a milestone name. Keep all failed and successful controls.

Require several agreeing indicators over long runs:

- sustained novelty beyond startup transients;
- lineage branching and persistence of descendants;
- new, measurable interactions or resource niches;
- robustness to seed changes and replay;
- ablation evidence that the claimed mechanism, not an artifact, produced the effect.

**Pass gate:** all indicators and their controls are retained in a public/inspectable audit. If one fails, report the narrower result instead of calling the system open-ended.

## Operational roadmap

The tooling supports the science; it does not replace it.

| Capability | Use | Guardrail |
| --- | --- | --- |
| Viewer | Inspect a single world and explain its current state. | Treat morphology text as a heuristic. |
| GUI grid and live views | Compare a controlled batch locally. | Limit workers/live previews so the desktop stays usable. |
| GPU particle screening | Find plausible persistence candidates quickly. | Recheck retained candidates with saved configs and accounting metrics. |
| Adaptive campaigns | Produce bounded, reproducible next-generation parameter panels from a completed report. | It optimizes experiments; it does not evolve simulated organisms. |
| JSON/snapshots/audits | Preserve provenance and review failures. | Never silently discard a negative control or failed run. |

## Immediate execution order

1. Let current runs finish and preserve their reports/snapshots unchanged.
2. Select a compact, fixed particle-persistence panel from completed reports.
3. Replay that panel with a fixed metric schedule and matched controls.
4. Add and run standardized particle damage/recovery tests only after the baseline panel is reproducible.
5. Make the go/no-go decision for conservative particle division from A2/A3 evidence.
6. In parallel, keep the field substrate as the current heredity/reproduction control and rerun its failed audit gates only when changes directly target those failures.

## Definition of success

Short term success is a trustworthy answer about particle individuality, including a well-documented negative answer if that is what the controls show.

Long term success is not a programmed creature. It is an archived population of locally produced forms with measured maintenance, heredity, ecological differentiation, and continuing viable novelty that survives skeptical controls.
