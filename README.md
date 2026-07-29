# Bev Novus

## Start here

Read [PROJECT_BRIEF.md](PROJECT_BRIEF.md) first for the current technical status, the research boundary between field and particle worlds, and a plain-language explanation. [ROADMAP.md](ROADMAP.md) is the evidence-gated execution plan. The retained field-world audit is [v2-audit.json](v2-audit.json); its failures are part of the record, not omissions.

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

The viewer selects a WebGPU compute engine when the browser and graphics driver
support it, with the original JavaScript engine as an automatic fallback. The
engine selector and live steps/second counter make the active path visible.

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
On Windows, double-click `run_experiment_gui.bat` to launch it; it uses the bundled
runtime when available so NumPy is found automatically.

The GUI Engine selector can also run the Phase 1 `Particle hybrid` mechanics through
the same parallel worker grid and visualization cards. Particle runs report live
particle count and finite mass drift; reproduction is intentionally deferred until
the particle prototype reaches its next milestone.
For particle runs, use the separate `Particle decay` field; its lower defaults avoid
applying the field engine's much larger per-step decay directly to particle masses.

The GUI also has an adaptive campaign workflow. Give it a completed particle JSON report, choose a bounded generation count, and it retains high-scoring configurations while perturbing declared safe parameter ranges. This schedules new experiments; it does not mean the particle bodies themselves are evolving. Use the focused and comparison visualization views to inspect saved configurations, and keep live previews off for large desktop campaigns.

For a broad screening sweep across all major rules, use the GUI's **Broad sweep**
button. Set the `Broad configs` field (256 by default); it samples that many
configurations with the selected seeds and uses the same workers, progress display,
visualizations, and JSON export as the normal grid. The standalone
`run_broad_sweep.bat` remains available for headless runs.

For a long unattended campaign, use the GUI's **Overnight campaign** button or
double-click `run_overnight_gpu.bat`. It screens 768 configurations across eight
seeds for 40,000 GPU steps, then CPU-replays the top 12 configurations for
500,000 steps each. The run writes `Results/overnight-gpu-sweep.json`.

The GUI defaults to three workers and the headless sweep to twelve. The optimized
step kernel makes these lower-CPU defaults faster than the previous four- and
sixteen-worker settings on the development machine.

### Optional GPU screening

Run `setup_gpu.bat` once, then launch the normal experiment GUI and choose
**GPU screen + replay**. GPU screening batches float32 worlds on an NVIDIA GPU,
corrects aggregate mass at each sample interval, and ranks persistence/field
diversity without making reproduction claims. The selected configurations are
then replayed through the unchanged float64 CPU model, where births, lineage,
viability, conservation, and snapshots remain authoritative. `Steps` controls
CPU replay length; `GPU screen steps`, `GPU batch`, and `Replay top` control the
screening stage. Exporting results preserves both screening and replay records.

The optional CUDA packages live in `.gpu-packages/` and are not committed. The
CPU runner remains available when CUDA is absent.

On the development RTX 3070, a 64-world screening batch measured about 28,800
world-steps/second while using roughly 0.7 host CPU core, versus about 3,700
world-steps/second for the three-worker CPU sweep. GPU figures are screening
throughput only; release claims still come from the CPU replays.
Override settings from a terminal, for example:

```powershell
run_broad_sweep.bat --configs 512 --steps 200000 --workers 16
```

## Roadmap and 2.0 audit

See [ROADMAP.md](ROADMAP.md) for the current evidence-gated sequence and [PROJECT_BRIEF.md](PROJECT_BRIEF.md) for the distinction between implemented tooling and demonstrated biology. Version 2.0 publishes the audit state of its field-world gates, including failures and null results.

## What 2.0 does not claim

Long-run open-endedness, robust multicellular individuality, and intrinsic ecological innovation remain empirical questions for longer experiments—not features asserted by this release.
