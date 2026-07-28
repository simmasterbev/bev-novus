"""Broad, reproducible parameter screening for Bev Novus."""

from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path

import numpy as np

from experiments import run_condition


RANGES = {
    "metabolism": (0.015, 0.035, 0.07), "body_yield": (0.30, 0.40, 0.50),
    "decay_rate": (0.02, 0.03, 0.04), "diffusion": (0.10, 0.30, 0.50),
    "waste_inhibition": (0.10, 0.30, 0.60), "recycle_rate": (0.03, 0.10, 0.20),
    "seed_interval": (20, 60, 120), "source_scale": (0.50, 1.50, 2.50),
    "steering": (1.0, 3.0, 5.0), "seed_fraction": (0.03, 0.08, 0.15),
    "mutation_scale": (0.005, 0.02, 0.05), "resource_patches": (3, 5, 9),
    "body_patches": (3, 5, 9), "resource_strength": (0.70, 1.15, 1.80),
    "body_strength": (0.50, 1.00, 1.50), "resource_regrowth": (0.005, 0.01, 0.03),
    "resource_capacity": (0.50, 1.00, 2.00), "waste_decay": (0.005, 0.02, 0.08),
    "waste_diffusion": (0.05, 0.20, 0.50), "dormancy_threshold": (0.02, 0.06, 0.15),
    "dormancy_cost": (0.05, 0.15, 0.40), "complexity_pressure": (0.0, 0.65, 1.50),
}
INTEGER_PARAMS = {"seed_interval", "resource_patches", "body_patches"}


def latin_hypercube(count: int, seed: int) -> list[dict]:
    rng = np.random.default_rng(seed)
    samples = {}
    for name, levels in RANGES.items():
        low, _, high = levels
        samples[name] = low + ((np.arange(count) + rng.random(count)) / count) * (high - low)
        rng.shuffle(samples[name])
    configs = []
    for index in range(count):
        config = {name: float(values[index]) for name, values in samples.items()}
        for name in INTEGER_PARAMS:
            config[name] = int(round(config[name]))
        configs.append(config)
    return configs


def run_one(job: dict) -> dict:
    result = run_condition(**job["config"], seed=job["seed"], steps=job["steps"],
                           sample_every=job["sample_every"], reproduce=job["reproduce"])
    return {"config_id": job["config_id"], "seed": job["seed"], **job["config"], **asdict(result)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a broad Latin-hypercube Bev Novus sweep.")
    parser.add_argument("--configs", type=int, default=256, help="sampled parameter configurations")
    parser.add_argument("--seeds", default="1,2,3", help="comma-separated replicate seeds")
    parser.add_argument("--steps", type=int, default=200000)
    parser.add_argument("--sample-every", type=int, default=5000)
    parser.add_argument("--workers", type=int, default=min(os.cpu_count() or 4, 16))
    parser.add_argument("--out", type=Path, default=Path("Results/broad-sweep.json"))
    parser.add_argument("--no-reproduction", action="store_true")
    args = parser.parse_args()
    if args.configs < 1 or args.steps < 1 or args.sample_every < 1:
        parser.error("configs, steps, and sample interval must be positive")
    seeds = [int(value.strip()) for value in args.seeds.split(",") if value.strip()]
    configs = latin_hypercube(args.configs, seed=7)
    jobs = [{"config_id": index + 1, "config": {"label": f"lhs-{index + 1:04d}", **config},
             "seed": seed, "steps": args.steps, "sample_every": args.sample_every,
             "reproduce": not args.no_reproduction}
            for index, config in enumerate(configs) for seed in seeds]
    results, started = [], time.perf_counter()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(run_one, job) for job in jobs]
        for complete, future in enumerate(as_completed(futures), 1):
            results.append(future.result())
            if complete % 10 == 0 or complete == len(jobs):
                args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
                elapsed = time.perf_counter() - started
                rate = complete / max(elapsed, 1e-9)
                print(f"completed {complete}/{len(jobs)} | {rate:.2f} runs/s | {args.out}", flush=True)
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
