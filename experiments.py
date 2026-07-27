"""Small, reproducible v1.1 experiment harness for Bev Novus."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from morrow import PatternCensus, World, ecology_metrics, evolvability_metrics


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
        "evolvability": {"status": "pass" if max(result.trait_diversity for result in results) > 0 else "fail", "max_trait_diversity": max(result.trait_diversity for result in results)},
        "open_endedness": {"status": "not-demonstrated", "reason": "requires sustained multi-metric novelty beyond this audit horizon"},
    }}


def run_condition(label: str, seed: int, steps: int = 480, *, mutate: bool = True,
                  recycle: bool = True, spatial: bool = True, reproduce: bool = True,
                  metabolism: float = 0.07, diffusion: float = 0.18) -> Result:
    world, census = World.seeded(seed=seed), PatternCensus()
    world.metabolism_rate, world.diffusion, world.autonomous_reproduction = metabolism, diffusion, reproduce
    if not mutate:
        world.mutation_mass[:] = world.body * 0.005
    if not recycle:
        world.resource_source[:] = 0.0
    if not spatial:
        world.resource_source[:] = 1.0
        world.resource[:] = world.resource.mean()
    baseline = world.total_mass
    census.update(world.components())
    for tick in range(steps):
        prior, start = dict(census.current), len(world.births)
        world.step(); census.update(world.components())
        for birth in world.births[start:]:
            if prior:
                birth.parent_id = min(prior, key=lambda ident: abs(prior[ident].trait - birth.parent_trait))
        world.assess_births(tick)
    eco, evo = ecology_metrics(world, census), evolvability_metrics(world, census)
    return Result(label, seed, len(census.current), len(world.births), int(evo["viable_births"]),
                  evo["trait_diversity"], eco["occupied_trait_niches"], abs(world.total_mass - baseline))


def sweep(steps: int = 480, seeds: tuple[int, ...] = (1, 2, 3)) -> list[Result]:
    results = []
    for metabolism in (0.05, 0.07, 0.09):
        for diffusion in (0.10, 0.18, 0.26):
            label = f"metabolism={metabolism:.2f}, diffusion={diffusion:.2f}"
            results.extend(run_condition(label, seed, steps, metabolism=metabolism, diffusion=diffusion) for seed in seeds)
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
