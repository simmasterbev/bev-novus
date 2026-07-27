# Morrow

Morrow is a small, inspectable artificial-life world inspired by Lenia, Flow-Lenia, Avida, and artificial chemistry research.

Version 0.4 reaches the first four research milestones:

- body matter moves through a local affinity field;
- resource is converted to body matter and waste;
- body matter decays into waste;
- all three fields conserve total mass under periodic boundaries;
- an above-threshold connected-component detector reports localized structures;
- a census counts observed pattern creation, persistence, and destruction;
- maintenance and local-damage probes compare resource-supported bodies with starvation and perturbation controls;
- a clearly labeled external reproduction scaffold transfers local body matter, copies a scalar trait, and applies mutation;
- birth records measure trait resemblance and short-horizon offspring viability;
- frames are written as portable PPM images with waste in red, body in green, and resource in blue.

The reproduction mechanism is an experimental bridge, not intrinsic self-reproduction. Pattern IDs are observations, not claims that the patterns are organisms; the system does not yet demonstrate evolution or open-endedness.

## Run

```powershell
python -m pip install -r requirements.txt
python morrow.py --steps 500 --every 100 --reproduce --probe
```

The run prints mass drift and writes frames to `output/`. Most image viewers can open PPM files; they can also be converted later if needed.

## Live view

Open `viewer.html` in a modern browser. It runs the three-field world continuously; green is body matter, blue resource, and red waste. Toggle the reproduction scaffold to compare its controlled lineage events with unassisted dynamics.

## Check

```powershell
python -m unittest -v
```

## Next milestone

Replace the external scaffold with intrinsically generated division or seed emission, then test whether it remains viable without an evaluator.
