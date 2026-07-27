"""Morrow 0.1 - a tiny conservative artificial-life world."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class World:
    body: np.ndarray
    resource: np.ndarray
    waste: np.ndarray
    metabolism_rate: float = 0.07
    body_yield: float = 0.72
    decay_rate: float = 0.012
    diffusion: float = 0.18
    steering: float = 2.0

    @classmethod
    def seeded(cls, height: int = 72, width: int = 96, seed: int = 1) -> "World":
        rng = np.random.default_rng(seed)
        y, x = np.mgrid[:height, :width]
        resource = np.zeros((height, width), dtype=float)
        body = np.zeros_like(resource)
        for _ in range(7):
            cy, cx = rng.uniform(0, height), rng.uniform(0, width)
            radius = rng.uniform(6, 16)
            resource += np.exp(-((y - cy) ** 2 + (x - cx) ** 2) / radius**2)
        for _ in range(5):
            cy, cx = rng.uniform(0, height), rng.uniform(0, width)
            radius = rng.uniform(2, 5)
            body += 0.55 * np.exp(-((y - cy) ** 2 + (x - cx) ** 2) / radius**2)
        return cls(body=body, resource=resource, waste=np.zeros_like(resource))

    @property
    def total_mass(self) -> float:
        return float((self.body + self.resource + self.waste).sum())

    def step(self) -> None:
        """Advance one fully local, periodic, mass-conserving update."""
        affinity = self._neighbor_mean(self.body) + 0.35 * self.resource - 0.45 * self.waste
        self.body = self._transport(self.body, affinity)

        intake = np.minimum(self.resource, self.metabolism_rate * self.body * self.resource)
        self.resource -= intake
        self.body += self.body_yield * intake
        self.waste += (1.0 - self.body_yield) * intake

        decay = self.decay_rate * self.body
        self.body -= decay
        self.waste += decay

    def localized_structures(self, threshold: float = 0.25, min_cells: int = 4) -> list[int]:
        """Return sizes of above-threshold body components on the periodic grid."""
        if not 0.0 < threshold <= 1.0 or min_cells < 1:
            raise ValueError("threshold must be in (0, 1] and min_cells must be positive")
        peak = self.body.max()
        if peak <= 0.0:
            return []
        mask = self.body >= threshold * peak
        seen = np.zeros_like(mask, dtype=bool)
        height, width = mask.shape
        sizes = []
        for start_y, start_x in zip(*np.nonzero(mask & ~seen)):
            if seen[start_y, start_x]:
                continue
            stack, size = [(start_y, start_x)], 0
            seen[start_y, start_x] = True
            while stack:
                y, x = stack.pop()
                size += 1
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = (y + dy) % height, (x + dx) % width
                    if mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            if size >= min_cells:
                sizes.append(size)
        return sorted(sizes, reverse=True)

    def _neighbor_mean(self, field: np.ndarray) -> np.ndarray:
        return (
            field
            + np.roll(field, 1, 0)
            + np.roll(field, -1, 0)
            + np.roll(field, 1, 1)
            + np.roll(field, -1, 1)
        ) / 5.0

    def _transport(self, mass: np.ndarray, affinity: np.ndarray) -> np.ndarray:
        directions = ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))
        logits = [np.ones_like(affinity)]
        for dy, dx in directions[1:]:
            neighbor = np.roll(affinity, (-dy, -dx), axis=(0, 1))
            logits.append(np.exp(self.steering * (neighbor - affinity)))
        weights = np.stack(logits)
        weights /= weights.sum(axis=0, keepdims=True)
        weights[0] = (1.0 - self.diffusion) * weights[0] + self.diffusion / 5.0
        weights[1:] = (1.0 - self.diffusion) * weights[1:] + self.diffusion / 5.0

        moved = np.zeros_like(mass)
        for weight, (dy, dx) in zip(weights, directions):
            moved += np.roll(mass * weight, (dy, dx), axis=(0, 1))
        return moved

    def write_ppm(self, path: Path) -> None:
        """Write a dependency-free RGB visualization: body=green, resource=blue, waste=red."""
        def scale(field: np.ndarray) -> np.ndarray:
            ceiling = max(float(np.quantile(field, 0.995)), 1e-9)
            return np.clip(field / ceiling, 0.0, 1.0)

        rgb = np.dstack((scale(self.waste), scale(self.body), scale(self.resource)))
        pixels = (255 * rgb).astype(np.uint8)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as stream:
            stream.write(f"P6\n{pixels.shape[1]} {pixels.shape[0]}\n255\n".encode())
            stream.write(pixels.tobytes())


def run(steps: int, every: int, output: Path, seed: int) -> World:
    world = World.seeded(seed=seed)
    baseline = world.total_mass
    for tick in range(steps + 1):
        if tick % every == 0:
            world.write_ppm(output / f"frame-{tick:05d}.ppm")
        if tick < steps:
            world.step()
    drift = abs(world.total_mass - baseline)
    print(f"steps={steps} mass={world.total_mass:.9f} drift={drift:.3e} structures={len(world.localized_structures())}")
    return world


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Morrow 0.1 world.")
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--every", type=int, default=100)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", type=Path, default=Path("output"))
    args = parser.parse_args()
    if args.steps < 0 or args.every < 1:
        parser.error("--steps must be non-negative and --every must be at least 1")
    run(args.steps, args.every, args.out, args.seed)


if __name__ == "__main__":
    main()
