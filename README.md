# Bev Novus

Bev Novus is a small, inspectable artificial-life world inspired by Lenia, Flow-Lenia, Avida, and artificial chemistry research.

Version 2.2 adds renewable ecology and dormancy on top of the initial roadmap audit and expanded experiment controls. The live viewer now exposes a parameter lab for:

- metabolism, body yield, decay, waste inhibition, recycling, diffusion, and steering;
- seed interval, seed fraction, mutation scale, and mutation/recycling toggles;
- deterministic starting-world seed, resource/body patch counts, patch strengths, and source scale.
- resource regrowth/capacity, waste decay/diffusion, and dormancy threshold/cost.
- complexity pressure, which rewards resource-supported cells embedded in connected neighborhoods;
- selectable viewer resolutions of 96×72, 144×108, and 192×144.

The same core rules are available from `morrow.py` flags, so browser exploration can be reproduced from the command line.

The world includes:

- body matter moves through a local affinity field;
- resource is converted to body matter and waste;
- body matter decays into waste;
- all three fields conserve total mass under periodic boundaries;
- an above-threshold connected-component detector reports localized structures;
- a census counts observed pattern creation, persistence, and destruction;
- maintenance and local-damage probes compare resource-supported bodies with starvation and perturbation controls;
- local resource-rich bodies autonomously emit offspring seeds and inherit a two-parameter description (behavior and mutability);
- birth records measure trait resemblance and short-horizon offspring viability;
- spatial resource recycling and waste inhibition create a minimal ecology with measurable patchiness and trait niches;
- resource patches can regrow toward a carrying capacity; waste can decay and diffuse; low-mass patterns can enter a low-cost dormant regime;
- lineage, diversity, novelty, and inherited mutation-rate measurements instrument evolvability experiments;
- frames are written as portable PPM images with waste in red, body in green, and resource in blue.

Pattern IDs are observations, not claims that the patterns are organisms. Bev Novus now has model-internal seed emission and heritable variation, but it does not yet demonstrate sustained open-ended evolution.

## Run

```powershell
python -m pip install -r requirements.txt
python morrow.py --steps 500 --every 100 --probe
```

The run prints mass drift and writes frames to `output/`. Most image viewers can open PPM files; they can also be converted later if needed.

## Live view

Open `viewer.html` in a modern browser. It runs the three-field world continuously; green is body matter, blue resource, and red waste. It reports observed structures and autonomous birth/viability events. Expand “World rules and starting configuration” to tune the rules; use “Apply starting world” after changing seed or patch settings. The panel includes the “High-Flux Oasis” preset and JSON config export/import.

For a reproducible custom run:

```powershell
python morrow.py --seed 12 --metabolism-rate 0.08 --waste-inhibition 0.6 --recycle-rate 0.04 --resource-patches 3 --body-patches 2 --source-scale 2.0
```

## Check

```powershell
python -m unittest -v
```

## v1.1 experiments

```powershell
python experiments.py --steps 480
```

This writes a reproducible sweep plus no-mutation, no-recycling, well-mixed, and no-reproduction controls to `experiment-report.json`.

Open `dashboard.html` and select that report to compare viable births, persistent patterns, and trait diversity.

Open `audit.html` to inspect the replicated 2.0 release gates and their retained failures.

## Local parallel experiment runner

Run `python experiment_gui.py` to open a small Tkinter tool. Enter comma-separated
values for seeds, body yield, and decay; choose the step count and worker count;
then run the Cartesian product. Results appear as each run finishes and can be
exported as JSON. The default grid matches the recent 200k-step persistence test.

## Roadmap and 2.0 audit

See `ROADMAP.md` for the full release sequence and test gates. Version 2.0 publishes the audit state of those gates, including failures and null results.

## What 2.0 does not claim

Long-run open-endedness, robust multicellular individuality, and intrinsic ecological innovation remain empirical questions for longer experiments—not features asserted by this release.
