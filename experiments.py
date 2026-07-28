"""Small, reproducible v1.1 experiment harness for Bev Novus."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from morrow import PatternCensus, World, collective_metrics, ecology_metrics, evolvability_metrics, individuality_metrics
from particle_prototype import HybridParticleWorld


@dataclass
class Result:
    label: str
    seed: int
    live: int
    births: int
    viable: int
    trait_diversity: float
    niches: float
    mass_drift: float
    compactness: float
    boundary_ratio: float
    identity_ambiguity: float
    groups: float


def _write_particle_ppm(world: HybridParticleWorld, path: Path) -> None:
    """Write a small compatible snapshot for the existing Tkinter viewer."""
    height, width = world.resource.shape
    body = np.zeros_like(world.resource)
    rows, columns = world._indices()
    for row, column, mass in zip(rows, columns, world.particle.masses):
        body[row, column] += mass
    scale = max(float(body.max()), float(world.resource.max()), float(world.waste.max()), 1e-9)
    pixels = np.stack((world.waste, body, world.resource), axis=-1)
    pixels = np.clip(pixels * 255.0 / scale, 0, 255).astype(np.uint8)
    with Path(path).open("wb") as handle:
        handle.write(f"P6\n{width} {height}\n255\n".encode("ascii"))
        handle.write(pixels.tobytes())


def _atomic_snapshot(path: Path, writer) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    writer(temporary)
    os.replace(temporary, path)


def run_particle_condition(label: str, seed: int, steps: int = 480, *, metabolism: float = 0.02,
                           body_yield: float = 0.72, decay_rate: float = 0.012,
                           resource_regrowth: float = 0.006, resource_capacity: float = 1.0,
                           body_patches: int = 5, body_strength: float = 0.55,
                           sample_every: int = 1, snapshot_path: Path | None = None,
                           live_snapshot_path: Path | None = None, live_snapshot_every: int = 1000,
                           **_: object) -> Result:
    """Run the Phase 1 hybrid mechanics with the GUI's common result contract."""
    count = max(16, body_patches * 12)
    world = HybridParticleWorld.seeded(seed=seed, count=count)
    world.metabolism = metabolism
    world.body_yield = body_yield
    world.resource_regrowth = resource_regrowth
    world.resource_capacity = resource_capacity
    world.waste_decay = 0.0
    world.particle.masses[:] = max(0.05, body_strength / 2.0)
    baseline = world.total_mass
    external_delta = 0.0
    if live_snapshot_path is not None:
        _atomic_snapshot(Path(live_snapshot_path), lambda path: _write_particle_ppm(world, path))
    for _step in range(steps):
        regrowth = resource_regrowth * world.source * np.maximum(resource_capacity - world.resource, 0.0)
        external_delta += float(regrowth.sum())
        world.step()
        if decay_rate > 0:
            decay = decay_rate * world.particle.masses
            world.particle.masses[:] = np.maximum(0.0, world.particle.masses - decay)
            rows, columns = world._indices()
            np.add.at(world.waste, (rows, columns), decay)
        if not (np.isfinite(world.particle.positions).all() and np.isfinite(world.total_mass)):
            raise FloatingPointError("particle hybrid produced a non-finite state")
        if live_snapshot_path is not None and (_step + 1) % max(1, live_snapshot_every) == 0:
            _atomic_snapshot(Path(live_snapshot_path), lambda path: _write_particle_ppm(world, path))
    if snapshot_path is not None:
        _atomic_snapshot(Path(snapshot_path), lambda path: _write_particle_ppm(world, path))
    live = int(np.count_nonzero(world.particle.masses > 0.05))
    compactness = float(min(1.0, live / max(count, 1)))
    return Result(label, seed, live, 0, 0, 0.0, 0.0,
                  abs(world.total_mass - baseline - external_delta), compactness, compactness, 0.0, 0.0)


def audit(steps: int = 1000, seeds: tuple[int, ...] = tuple(range(1, 11))) -> dict:
    results = [run_condition("audit", seed, steps) for seed in seeds]
    drifts = [result.mass_drift for result in results]
    baseline = run_condition("baseline", seeds[0], steps)
    no_reproduction = run_condition("no reproduction", seeds[0], steps, reproduce=False)
    return {"steps": steps, "seeds": list(seeds), "results": [asdict(result) for result in results], "gates": {
        "accounting": {"status": "pass" if max(drifts) < 1e-8 else "fail", "max_drift": max(drifts)},
        "replication": {"status": "pass" if len(results) >= 10 else "fail", "runs": len(results)},
        "persistence": {"status": "fail" if np.median([result.live for result in results]) == 0 else "observe", "median_live": float(np.median([result.live for result in results]))},
        "reproduction_effect": {"status": "pass" if baseline.births > no_reproduction.births else "observe", "with_reproduction": baseline.births, "without": no_reproduction.births},
        "identity": {"status": "pass" if max(result.identity_ambiguity for result in results) / max(sum(result.births for result in results), 1) < .05 else "fail", "ambiguous": max(result.identity_ambiguity for result in results)},
        "individuality": {"status": "observe", "median_compactness": float(np.median([result.compactness for result in results])), "median_boundary_ratio": float(np.median([result.boundary_ratio for result in results]))},
        "ecology": {"status": "observe", "spatial_runs": sum(result.niches > 0 for result in results), "well_mixed_control": no_reproduction.live},
        "collective": {"status": "not-demonstrated", "multi_core_runs": sum(result.groups > 0 for result in results)},
        "evolvability": {"status": "pass" if max(result.trait_diversity for result in results) > 0 else "fail", "max_trait_diversity": max(result.trait_diversity for result in results)},
        "open_endedness": {"status": "not-demonstrated", "reason": "requires sustained multi-metric novelty beyond this audit horizon"},
    }}


def run_condition(label: str, seed: int, steps: int = 480, *, mutate: bool = True,
                  recycle: bool = True, spatial: bool = True, reproduce: bool = True,
                  metabolism: float = 0.07, diffusion: float = 0.18, waste_inhibition: float = 0.45,
                  recycle_rate: float = 0.025, seed_interval: int = 60, source_scale: float = 1.5,
                  steering: float = 2.0, seed_fraction: float = 0.22, mutation_scale: float = 0.01,
                  resource_patches: int = 7, body_patches: int = 5,
                  resource_strength: float = 1.0, body_strength: float = 0.55,
                  resource_regrowth: float = 0.006, resource_capacity: float = 1.0,
                  waste_decay: float = 0.002, waste_diffusion: float = 0.12,
                  dormancy_threshold: float = 0.08, dormancy_cost: float = 0.15,
                  body_yield: float = 0.72, decay_rate: float = 0.012, complexity_pressure: float = 0.35,
                  sample_every: int = 1, snapshot_path: Path | None = None,
                  live_snapshot_path: Path | None = None, live_snapshot_every: int = 1000) -> Result:
    world, census = World.seeded(seed=seed, source_scale=source_scale, resource_patches=resource_patches,
                                 body_patches=body_patches, resource_strength=resource_strength,
                                 body_strength=body_strength), PatternCensus()
    world.metabolism_rate, world.diffusion, world.autonomous_reproduction = metabolism, diffusion, reproduce
    world.steering = steering
    world.waste_inhibition, world.recycle_rate, world.seed_interval = waste_inhibition, recycle_rate, seed_interval
    world.seed_fraction, world.mutation_scale = seed_fraction, mutation_scale
    world.resource_regrowth, world.resource_capacity = resource_regrowth, resource_capacity
    world.waste_decay, world.waste_diffusion = waste_decay, waste_diffusion
    world.dormancy_threshold, world.dormancy_cost = dormancy_threshold, dormancy_cost
    world.body_yield, world.decay_rate, world.complexity_pressure = body_yield, decay_rate, complexity_pressure
    if not mutate:
        world.mutation_mass[:] = world.body * 0.005
    if not recycle:
        world.resource_source[:] = 0.0
    if not spatial:
        world.resource_source[:] = 1.0
        world.resource[:] = world.resource.mean()
    baseline = world.total_mass
    if live_snapshot_path is not None:
        _atomic_snapshot(Path(live_snapshot_path), world.write_ppm)
    census.update(world.components())
    registered_births = 0
    for tick in range(steps):
        prior = dict(census.current)
        world.step()
        if tick % max(1, sample_every) == 0 or tick == steps - 1:
            census.update(world.components())
        for birth in world.births[registered_births:]:
            if prior:
                birth.parent_id = min(prior, key=lambda ident: abs(prior[ident].trait - birth.parent_trait))
            census.register_birth(birth, census.current)
        registered_births = len(world.births)
        world.assess_births(tick)
        if live_snapshot_path is not None and (tick + 1) % max(1, live_snapshot_every) == 0:
            _atomic_snapshot(Path(live_snapshot_path), world.write_ppm)
    eco, evo = ecology_metrics(world, census), evolvability_metrics(world, census)
    individual, collective = individuality_metrics(world, census), collective_metrics(world, census)
    if snapshot_path is not None:
        _atomic_snapshot(Path(snapshot_path), world.write_ppm)
    return Result(label, seed, len(census.current), len(world.births), int(evo["viable_births"]),
                  evo["trait_diversity"], eco["occupied_trait_niches"], abs(world.total_mass - baseline - world.external_delta),
                  individual["compactness"], individual["boundary_ratio"], individual["ambiguous_identity"], collective["multi_core_groups"])


def sweep(steps: int = 480, seeds: tuple[int, ...] = (1, 2, 3)) -> list[Result]:
    results = []
    for metabolism in (0.05, 0.07, 0.09):
        for diffusion in (0.10, 0.18, 0.26):
            for source_scale, seed_interval in ((1.0, 40), (1.5, 60), (2.0, 90)):
                for waste_inhibition, recycle_rate in ((0.25, 0.01), (0.45, 0.025), (0.65, 0.05)):
                    label = (f"metabolism={metabolism:.2f}, diffusion={diffusion:.2f}, patch={source_scale:.1f}, "
                             f"interval={seed_interval}, waste={waste_inhibition:.2f}, recycle={recycle_rate:.3f}")
                    results.extend(run_condition(label, seed, steps, metabolism=metabolism, diffusion=diffusion,
                                                 source_scale=source_scale, seed_interval=seed_interval,
                                                 waste_inhibition=waste_inhibition, recycle_rate=recycle_rate) for seed in seeds)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Bev Novus v1.1 controls and parameter sweep.")
    parser.add_argument("--steps", type=int, default=480)
    parser.add_argument("--out", type=Path, default=Path("experiment-report.json"))
    parser.add_argument("--audit", action="store_true", help="run the replicated 2.0 gate audit")
    args = parser.parse_args()
    if args.audit:
        report = audit(max(args.steps, 1000))
        args.out.write_text(json.dumps(report, indent=2))
        print(json.dumps(report["gates"], indent=2))
        return
    controls = [run_condition("baseline", 1, args.steps), run_condition("no mutation", 1, args.steps, mutate=False),
                run_condition("no recycling", 1, args.steps, recycle=False), run_condition("well mixed", 1, args.steps, spatial=False),
                run_condition("no reproduction", 1, args.steps, reproduce=False)]
    results = controls + sweep(args.steps)
    args.out.write_text(json.dumps([asdict(result) for result in results], indent=2))
    best = max(results, key=lambda result: (result.viable, result.live, result.trait_diversity))
    print(f"best={best.label} seed={best.seed} viable={best.viable} live={best.live} diversity={best.trait_diversity:.3f}")


if __name__ == "__main__":
    main()
