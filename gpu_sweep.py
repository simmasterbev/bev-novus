"""Optional GPU screening plus authoritative CPU replay for Bev Novus."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Callable

import numpy as np

from broad_sweep import latin_hypercube
from experiments import run_condition
from morrow import World


Progress = Callable[[str, int, int, str], None]
MIN_SCREEN_MASS = 0.1


def safe_trait_spread(xp, mass, variance):
    """Ignore variance from numerically empty worlds during screening."""
    return xp.where(mass >= MIN_SCREEN_MASS, xp.sqrt(xp.maximum(variance, 0.0)), 0.0)


def load_cupy():
    packages = Path(__file__).with_name(".gpu-packages")
    cuda = packages / "nvidia" / "cu13"
    if packages.exists() and str(packages) not in sys.path:
        sys.path.insert(0, str(packages))
    if cuda.exists():
        os.environ.setdefault("CUDA_PATH", str(cuda))
        os.environ["PATH"] = str(cuda / "bin" / "x86_64") + os.pathsep + os.environ.get("PATH", "")
    try:
        import cupy as cp
        cp.cuda.runtime.getDeviceCount()
        return cp
    except Exception as error:
        raise RuntimeError("GPU runtime unavailable. Run setup_gpu.bat first.") from error


class GpuBatch:
    """Float32 screening model; reproduction is intentionally deferred to CPU replay."""

    PARAMS = ("metabolism", "body_yield", "decay_rate", "diffusion", "waste_inhibition",
              "recycle_rate", "resource_regrowth", "resource_capacity", "waste_decay",
              "waste_diffusion", "dormancy_threshold", "dormancy_cost", "complexity_pressure")

    def __init__(self, jobs: list[dict]) -> None:
        self.cp = load_cupy()
        worlds = []
        for job in jobs:
            config = job["config"]
            world = World.seeded(seed=job["seed"], source_scale=config["source_scale"],
                                 resource_patches=config["resource_patches"], body_patches=config["body_patches"],
                                 resource_strength=config["resource_strength"], body_strength=config["body_strength"])
            if not job.get("recycle", True):
                world.resource_source[:] = 0.0
            if not job.get("spatial", True):
                world.resource_source[:] = 1.0
                world.resource[:] = world.resource.mean()
            worlds.append(world)
        cp = self.cp
        stack = lambda name: cp.asarray(np.stack([getattr(world, name) for world in worlds]), dtype=cp.float32)
        self.body, self.resource, self.waste = stack("body"), stack("resource"), stack("waste")
        self.trait, self.mutation, self.source = stack("trait_mass"), stack("mutation_mass"), stack("resource_source")
        self.external = cp.zeros_like(self.body)
        self.params = {name: cp.asarray([job["config"][name] for job in jobs], dtype=cp.float32)[:, None, None]
                       for name in self.PARAMS}
        self.initial_mass = cp.sum(self.body + self.resource + self.waste, axis=(1, 2), dtype=cp.float64)
        self.samples = 0
        self.alive_samples = cp.zeros(len(jobs), dtype=cp.float32)

    def neighbor(self, field):
        cp = self.cp
        return (field + cp.roll(field, 1, 1) + cp.roll(field, -1, 1)
                + cp.roll(field, 1, 2) + cp.roll(field, -1, 2)) * self.cp.float32(0.2)

    def step(self) -> None:
        cp, p = self.cp, self.params
        neighbor_body = self.neighbor(self.body)
        affinity = (1.0 + p["complexity_pressure"]) * neighbor_body + 0.35 * self.resource - p["waste_inhibition"] * self.waste
        traits = cp.where(self.body > 1e-12, self.trait / cp.maximum(self.body, 1e-12), 0.5)
        steering = 0.5 + 3.0 * traits
        scores = cp.stack((cp.zeros_like(affinity),
                           steering * (cp.roll(affinity, -1, 1) - affinity),
                           steering * (cp.roll(affinity, 1, 1) - affinity),
                           steering * (cp.roll(affinity, -1, 2) - affinity),
                           steering * (cp.roll(affinity, 1, 2) - affinity)), axis=1)
        scores -= scores.max(axis=1, keepdims=True)
        cp.clip(scores, -60.0, 0.0, out=scores); cp.exp(scores, out=scores)
        scores *= (1.0 - p["diffusion"][:, None]) / scores.sum(axis=1, keepdims=True)
        scores += p["diffusion"][:, None] * 0.2
        masses = cp.stack((self.body, self.trait, self.mutation), axis=1)
        moved = sum(cp.roll(masses * scores[:, direction, None], shift, axis=(2, 3))
                    for direction, shift in enumerate(((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))))
        moved_body, moved_trait, moved_mutation = moved[:, 0], moved[:, 1], moved[:, 2]
        traits = cp.where(moved_body > 1e-12, moved_trait / cp.maximum(moved_body, 1e-12), 0.5)
        neighbor_body = self.neighbor(moved_body)
        connectedness = cp.where(moved_body + neighbor_body > 1e-12,
                                 neighbor_body / cp.maximum(moved_body + neighbor_body, 1e-12), 0.0)
        intake = cp.minimum(self.resource, p["metabolism"] * (0.5 + traits) * moved_body * self.resource
                            * (1.0 + p["complexity_pressure"] * connectedness))
        self.resource -= intake
        growth = p["body_yield"] * intake
        self.body = moved_body + growth
        self.trait = moved_trait + traits * growth
        self.mutation = moved_mutation
        self.waste += (1.0 - p["body_yield"]) * intake
        decay = p["decay_rate"] * self.body * cp.where(self.body < p["dormancy_threshold"], p["dormancy_cost"], 1.0)
        self.body -= decay; self.trait -= traits * decay; self.waste += decay
        regrown = p["resource_regrowth"] * self.source * cp.maximum(p["resource_capacity"] - self.resource, 0.0)
        self.resource += regrown
        cleaned = p["waste_decay"] * self.waste
        self.waste -= cleaned
        self.external += regrown - cleaned
        self.waste = (1.0 - p["waste_diffusion"]) * self.waste + p["waste_diffusion"] * self.neighbor(self.waste)
        recycled = cp.minimum(self.waste, p["recycle_rate"] * self.source * self.waste)
        self.waste -= recycled; self.resource += recycled

    def correct_and_measure(self) -> list[dict]:
        cp = self.cp
        expected = self.initial_mass + cp.sum(self.external, axis=(1, 2), dtype=cp.float64)
        current = cp.sum(self.body + self.resource + self.waste, axis=(1, 2), dtype=cp.float64)
        correction = (expected - current) / (self.body.shape[1] * self.body.shape[2])
        self.resource += correction.astype(cp.float32)[:, None, None]
        corrected = cp.sum(self.body + self.resource + self.waste, axis=(1, 2), dtype=cp.float64)
        peak = self.body.max(axis=(1, 2))
        active = (self.body >= peak[:, None, None] * 0.25).sum(axis=(1, 2))
        mass = self.body.sum(axis=(1, 2), dtype=cp.float64)
        mean_trait = self.trait.sum(axis=(1, 2), dtype=cp.float64) / cp.maximum(mass, 1e-12)
        trait_field = cp.where(self.body > 1e-12, self.trait / cp.maximum(self.body, 1e-12), 0.5)
        variance = cp.sum(self.body * (trait_field - mean_trait[:, None, None]) ** 2,
                          axis=(1, 2), dtype=cp.float64) / cp.maximum(mass, 1e-12)
        alive = (active >= 4) & (mass > 0.1)
        self.alive_samples += alive
        self.samples += 1
        trait_spread = safe_trait_spread(cp, mass, variance)
        score = self.alive_samples / self.samples + cp.log1p(active) * 0.1 + trait_spread
        finite = cp.isfinite(mass) & cp.isfinite(variance) & cp.isfinite(corrected)
        score = cp.where(finite, score, -1e30)
        values = cp.asnumpy(cp.stack((cp.where(finite, mass, 0.0), cp.where(finite, active, 0),
                                     cp.where(finite, trait_spread, 0.0),
                                     cp.where(finite, abs(corrected - expected), 1e30), score, finite), axis=1))
        return [{"body_mass": float(row[0]), "active_cells": int(row[1]), "trait_spread": float(row[2]),
                 "mass_drift": float(row[3]), "screen_score": float(row[4]), "finite": bool(row[5])} for row in values]


def replay_one(job: dict) -> dict:
    try:
        result = run_condition(job["label"], job["seed"], job["steps"], sample_every=job["sample_every"],
                               snapshot_path=job["snapshot_path"], **job["controls"], **job["config"])
        return {"config_id": job["config_id"], **asdict(result), "_snapshot_path": str(job["snapshot_path"])}
    except Exception as error:  # preserve the rest of a long campaign if one replay fails
        return {"config_id": job["config_id"], "label": f"ERROR: {job['label']}", "seed": job["seed"],
                "live": 0, "births": 0, "viable": 0, "trait_diversity": 0.0, "niches": 0.0,
                "mass_drift": float("nan"), "compactness": 0.0, "boundary_ratio": 0.0,
                "identity_ambiguity": 0.0, "groups": 0.0, "error": repr(error),
                "_snapshot_path": str(job["snapshot_path"])}


def screen_and_replay(configs: list[dict], seeds: list[int], screen_steps: int, sample_every: int,
                      batch_size: int, replay_top: int, replay_steps: int, replay_workers: int,
                      output_dir: Path, progress: Progress | None = None,
                      stopped: Callable[[], bool] | None = None, controls: dict | None = None) -> dict:
    controls = controls or {"reproduce": True, "mutate": True, "recycle": True, "spatial": True}
    jobs = [{"config_id": index + 1, "config": config, "seed": seed, **controls}
            for index, config in enumerate(configs) for seed in seeds]
    screening = []
    started = time.perf_counter()
    for offset in range(0, len(jobs), batch_size):
        if stopped and stopped():
            break
        batch_jobs = jobs[offset:offset + batch_size]
        batch = GpuBatch(batch_jobs)
        metrics = []
        for tick in range(screen_steps):
            batch.step()
            if (tick + 1) % sample_every == 0 or tick + 1 == screen_steps:
                metrics = batch.correct_and_measure()
                if progress:
                    progress("gpu", offset, len(jobs), f"GPU batch {offset // batch_size + 1}: step {tick + 1}/{screen_steps}")
                if stopped and stopped():
                    break
        for job, metric in zip(batch_jobs, metrics):
            screening.append({"config_id": job["config_id"], "seed": job["seed"], **job["config"], **metric})
        if progress:
            progress("gpu", min(offset + len(batch_jobs), len(jobs)), len(jobs), "GPU screening")
    by_config = {}
    for row in screening:
        by_config.setdefault(row["config_id"], []).append(row["screen_score"])
    selected = [ident for ident, _ in sorted(by_config.items(), key=lambda item: np.mean(item[1]), reverse=True)[:replay_top]]
    output_dir.mkdir(parents=True, exist_ok=True)
    replay_jobs = []
    for ident in selected:
        config = configs[ident - 1]
        for seed in seeds:
            replay_jobs.append({"config_id": ident, "label": f"gpu-replay-{ident:04d}", "seed": seed,
                                "steps": replay_steps, "sample_every": sample_every, "config": config,
                                "controls": controls,
                                "snapshot_path": output_dir / f"gpu-replay-{ident:04d}-seed-{seed}.ppm"})
    replays = []
    with ProcessPoolExecutor(max_workers=max(1, replay_workers)) as pool:
        future_jobs = {pool.submit(replay_one, job): job for job in replay_jobs}
        for complete, future in enumerate(as_completed(future_jobs), 1):
            if stopped and stopped():
                for pending in future_jobs:
                    pending.cancel()
                break
            job = future_jobs[future]
            try:
                replays.append(future.result())
            except Exception as error:  # defensive guard around worker/pool failures
                replays.append({"config_id": job["config_id"], "label": f"ERROR: {job['label']}",
                                "seed": job["seed"], "live": 0, "births": 0, "viable": 0,
                                "trait_diversity": 0.0, "niches": 0.0, "mass_drift": float("nan"),
                                "compactness": 0.0, "boundary_ratio": 0.0, "identity_ambiguity": 0.0,
                                "groups": 0.0, "error": repr(error),
                                "_snapshot_path": str(job["snapshot_path"])})
            if progress:
                progress("cpu", complete, len(replay_jobs), "Authoritative CPU replay")
    return {"backend": "gpu-float32-screening+cpu-float64-replay", "screening_claims_births": False,
            "screen_steps": screen_steps, "replay_steps": replay_steps, "selected_config_ids": selected,
            "elapsed_seconds": time.perf_counter() - started, "screening": screening, "replays": replays}


def main() -> None:
    parser = argparse.ArgumentParser(description="GPU screen broad configurations, then CPU-replay finalists.")
    parser.add_argument("--configs", type=int, default=64)
    parser.add_argument("--seeds", default="1,2,3")
    parser.add_argument("--screen-steps", type=int, default=20000)
    parser.add_argument("--replay-steps", type=int, default=200000)
    parser.add_argument("--sample-every", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--top", type=int, default=8)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--out", type=Path, default=Path("Results/gpu-sweep.json"))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        regression_mass = np.asarray([0.0, MIN_SCREEN_MASS])
        regression_variance = np.asarray([100.0, 4.0])
        assert np.allclose(safe_trait_spread(np, regression_mass, regression_variance), [0.0, 2.0])
        batch = GpuBatch([{"config_id": 1, "config": latin_hypercube(1, 7)[0], "seed": 1}])
        for _ in range(10):
            batch.step()
        metric = batch.correct_and_measure()[0]
        assert metric["finite"] and metric["mass_drift"] < 0.01, metric
        print(f"GPU self-test passed: {metric}")
        return
    seeds = [int(value) for value in args.seeds.split(",") if value.strip()]
    report = screen_and_replay(latin_hypercube(args.configs, 7), seeds, args.screen_steps, args.sample_every,
                               args.batch_size, args.top, args.replay_steps, args.workers,
                               args.out.parent / "gpu-snapshots",
                               lambda stage, done, total, message: print(f"{stage}: {done}/{total} {message}", flush=True))
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
