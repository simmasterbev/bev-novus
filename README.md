# Bev Novus

Bev Novus is a small, inspectable artificial-life world inspired by Lenia, Flow-Lenia, Avida, and artificial chemistry research.

Version 1.0 completes the initial research roadmap:

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

Open `viewer.html` in a modern browser. It runs the three-field world continuously; green is body matter, blue resource, and red waste. It reports observed structures and autonomous birth/viability events.

## Check

```powershell
python -m unittest -v
```

## What v1 does not claim

Long-run open-endedness, robust multicellular individuality, and intrinsic ecological innovation remain empirical questions for longer experiments—not features asserted by this release.
