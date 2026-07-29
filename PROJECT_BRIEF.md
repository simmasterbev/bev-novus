# Bev Novus - Project Brief

> Current project summary, technical status, and research direction. Updated 2026-07-29 from the tracked implementation, `v2-audit.json`, and the local experiment tooling. This is the canonical orientation document; it is not evidence that any open-ended-evolution claim has passed.

## One-sentence description

Bev Novus is a reproducible artificial-life laboratory that asks whether simple local rules for matter, resources, waste, movement, inheritance, and ecology can produce increasingly life-like organization without hand-designing the organisms.

## Why this project is interesting

Most simulations either make creatures directly or make pretty patterns. Bev Novus is trying to study the difficult middle ground: can a world make its own persistent, resource-dependent, heritable forms from local physics?

That makes it interesting in three ways:

1. **It separates appearance from evidence.** A moving blob is a pattern; it is not automatically an organism. The project measures persistence, repair, reproduction, lineage, heredity, and ecological differentiation separately.
2. **It keeps the world causal.** Resource enters locally, bodies consume it, waste inhibits or recycles, and reproduction moves existing mass. The model avoids an invisible global fitness score.
3. **It is built as a laboratory.** Seeds, parameters, controls, snapshots, GPU screening, CPU reference runs, and audit gates make surprising results inspectable rather than anecdotal.

## What exists now

### 1. Field world - the current evolutionary control

The field world is a periodic 2D grid with three coupled quantities at every cell:

| Quantity | Role |
| --- | --- |
| Body | Structural material that moves, grows, decays, and can form connected components. |
| Resource | Usable environmental material that supports growth and can regrow toward local capacity. |
| Waste | Inhibitory by-product that diffuses, decays, and can partly recycle into resource. |

Body moves toward a locally computed affinity field. Its movement is local and mass-conserving under periodic boundaries. It consumes resource, converts a configurable fraction into more body, and transfers the remainder plus decay into waste. Bodies can enter a lower-cost dormant regime at low mass.

This substrate also contains the current seed-emission mechanism, trait and mutability fields, birth records, parent/child trait values, delayed viability assessment, connected-component census, repair probes, and ecology/individuality metrics. It is therefore the only current substrate that can support a real heredity or reproduction test.

### 2. Particle hybrid - the current physics and persistence testbed

The particle hybrid represents body material as individual particles coupled to grid resource and waste fields. Particles have position, mass, short-range repulsion, medium-range attraction, drag, mobility, resource taxis, and waste avoidance. The GPU runner batches compatible worlds, keeps conserved quantities in float64, and uses float32 force/position math for throughput.

The particle hybrid is useful because it can test cohesion, movement, resource coupling, and physical persistence in a body representation different from the field control. It currently reports live particles, body mass, finite state, compactness, and accounting drift.

**Important boundary:** particle reproduction, particle lineage, and particle trait diversity are not implemented. Its birth/viability values are therefore zero by design. It is not yet an evolutionary particle world.

### 3. Experiment and discovery tooling

The project currently includes:

- a browser viewer with JavaScript, WebGPU field, and Particle hybrid modes;
- a local Tkinter experiment runner with CPU grids, GPU screening, live views, single-run focus, and comparison mode;
- GPU particle campaigns that group worlds by particle count before batching;
- configuration export/import and preset campaigns;
- bounded adaptive iteration: rank a finished particle report, retain elites, perturb safe parameter ranges, and run a selected number of new generations;
- result JSON, PPM snapshots, dashboards, audits, and unit tests.

## Technical architecture

```text
seed + parameters
        |
        v
world substrate -----------------------> viewer / snapshots
  |                                      |
  |-- field body/resource/waste          |-- human inspection
  |-- or particle body + fields          |-- morphology heuristics
        |
        v
metrics and event records
  |-- accounting, persistence, repair
  |-- birth/lineage/heredity (field only)
  |-- ecology, diversity, novelty
        |
        v
experiment runner -> controls / replays / adaptive next generation
```

### Conservation and accounting

The project treats accounting as a prerequisite, not a nice-to-have. A world cannot be interpreted biologically if mass appears from numerical error. Regrowth and waste decay are recorded as external changes; transport and conversion are expected to conserve material within numerical tolerance.

### Identity and observation

Connected components and pattern IDs are observations. They help ask whether a localized form persists, splits, merges, repairs, or disappears. They do not assert that the form is an organism. Identity ambiguity is logged separately because merge/split events can make a naive ID misleading.

### Reproduction and heredity

In the field world, seed emission transfers local parent mass to an offset child seed, passes trait and mutability values with bounded mutation, and later checks short-horizon viability. This is a scaffold for testing heredity, not proof of sustained Darwinian evolution.

### Search and adaptive iteration

GPU runs are used to search many parameter combinations quickly. The adaptive loop is deliberately bounded: it keeps high-scoring candidates, perturbs them inside declared ranges, retains unchanged elites, stores each generation, and requires later replay/audit. It is an experiment scheduler, not an evolutionary claim about the simulated entities.

## Evidence state and honest non-claims

The tracked `v2-audit.json` shows that the earlier field audit passed accounting and 10-seed replication gates, but failed the persistence and evolvability gates at its 1,000-step horizon. It also did not demonstrate collective individuality or open-endedness.

Therefore Bev Novus currently **does not claim**:

- persistent organism-like individuals across the required controls;
- robust repair as a metabolism-dependent phenomenon;
- particle reproduction or particle evolution;
- stable ecological coexistence or niche differentiation;
- heritable selection effects across long lineages;
- open-ended evolution.

The right current claim is narrower: Bev Novus is an instrumented, reproducible artificial-chemistry and particle-physics testbed with a field-based reproduction scaffold and a fast particle-persistence search path.

## Imagined future state

The compelling future is not a game full of scripted creatures. It is a world where the same local rules can sometimes produce different durable strategies:

- compact bodies that conserve mass and repair damage;
- mobile bodies that seek one resource regime and avoid another;
- lineages whose inherited differences predict survival or reproduction;
- multiple resource strategies that coexist because they occupy different niches;
- occasional higher-level groups that outperform separated members;
- a continuing stream of viable, measurable novelty that survives ablation tests.

If that happens, the project becomes a research platform for asking how individuality, ecology, heredity, and evolvability arise together. If it does not happen, the failed controls are still valuable evidence about which ingredients are insufficient.

## The next decisive question

Before adding more complexity, establish whether particle bodies can become resource-supported, bounded, repairable individuals under controls. If they cannot, adding signals, extra chemistry, or more mutation would decorate an unstable substrate rather than solve the core problem.

See [ROADMAP.md](ROADMAP.md) for the evidence-gated path.

## Explain it to a five-year-old

Imagine a giant pretend pond made of tiny squares.

- Blue stuff is food.
- Green stuff is soft body-stuff.
- Red stuff is yucky leftovers.
- Green stuff can move toward food, eat it, grow, and make leftovers.
- Sometimes green stuff makes a little baby blob by giving it some of its own stuff.

We are not telling the blobs how to be animals. We are making the pond rules and watching carefully to see what the blobs can figure out. We keep score so we do not fool ourselves: did a blob really stay alive, fix itself, make a baby, and have babies that are a little different?

Right now we have a very good pretend pond and a fast way to try lots of pond rules. We are still trying to find out whether the blobs can become little living teams all by themselves.

## Document map

| Document | Use it for |
| --- | --- |
| `PROJECT_BRIEF.md` | Current orientation, technical status, future vision, and plain-language explanation. |
| `ROADMAP.md` | Current evidence-gated execution plan. |
| `README.md` | Installation, viewer, GUI, and command-line usage. |
| `Artificial_Life_Reading_Notes.md` | Source-by-source reading record and design inferences. |
| `Artificial_Life_Context.md` | Broad conceptual synthesis of the initial reading set. |
| `Artificial_Life_Deep_Research_Dive.md` | Extended research questions and future architectures. |
| `Our_ALife_World_Design.md` | Historical design specification; compare against the current brief before treating a section as implemented. |
