"""Minimal overdamped particle mechanics prototype for Bev Novus Phase 1."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class ParticleWorld:
    """Periodic, short-range particle world; resource/waste coupling comes later."""

    positions: np.ndarray
    width: float = 96.0
    height: float = 72.0
    masses: np.ndarray | None = None
    velocities: np.ndarray | None = None
    attraction: float = 0.8
    repulsion: float = 2.0
    interaction_radius: float = 6.0
    repulsion_radius: float = 1.5
    mobility: float = 1.0
    drag: float = 1.0
    timestep: float = 0.1
    _last_forces: np.ndarray = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.positions = np.asarray(self.positions, dtype=float).copy()
        if self.positions.ndim != 2 or self.positions.shape[1] != 2:
            raise ValueError("positions must have shape (n, 2)")
        count = len(self.positions)
        self.masses = np.ones(count, dtype=float) if self.masses is None else np.asarray(self.masses, dtype=float).copy()
        self.velocities = np.zeros((count, 2), dtype=float) if self.velocities is None else np.asarray(self.velocities, dtype=float).copy()
        if self.masses.shape != (count,) or self.velocities.shape != (count, 2):
            raise ValueError("masses and velocities must match the particle count")
        if np.any(self.masses <= 0) or self.interaction_radius <= self.repulsion_radius <= 0:
            raise ValueError("masses and interaction radii must be positive and ordered")
        self.positions[:, 0] %= self.height
        self.positions[:, 1] %= self.width
        self._last_forces = np.zeros_like(self.positions)

    @classmethod
    def seeded(cls, seed: int = 1, count: int = 32, width: float = 96.0, height: float = 72.0) -> "ParticleWorld":
        rng = np.random.default_rng(seed)
        center = np.array([height / 2, width / 2])
        positions = center + rng.normal(0.0, 2.0, size=(count, 2))
        return cls(positions, width=width, height=height)

    def _cell_size(self) -> float:
        return self.interaction_radius

    def _bins(self) -> dict[tuple[int, int], list[int]]:
        size = self._cell_size()
        columns, rows = max(1, int(self.width / size)), max(1, int(self.height / size))
        bins: dict[tuple[int, int], list[int]] = {}
        for index, (y, x) in enumerate(self.positions):
            key = (int(y / size) % rows, int(x / size) % columns)
            bins.setdefault(key, []).append(index)
        return bins

    def _nearby(self, index: int, bins: dict[tuple[int, int], list[int]]) -> list[int]:
        size = self._cell_size()
        columns, rows = max(1, int(self.width / size)), max(1, int(self.height / size))
        y, x = self.positions[index]
        cell = (int(y / size) % rows, int(x / size) % columns)
        candidates: set[int] = set()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                candidates.update(bins.get(((cell[0] + dy) % rows, (cell[1] + dx) % columns), ()))
        return sorted(candidates - {index})

    def forces(self) -> np.ndarray:
        """Return local pair forces using a periodic minimum-image displacement."""
        forces = np.zeros_like(self.positions)
        bins = self._bins()
        bounds = np.array([self.height, self.width])
        for index, position in enumerate(self.positions):
            for neighbor in self._nearby(index, bins):
                delta = self.positions[neighbor] - position
                delta -= np.round(delta / bounds) * bounds
                distance = float(np.linalg.norm(delta))
                if distance <= 1e-12 or distance >= self.interaction_radius:
                    continue
                direction = delta / distance
                if distance < self.repulsion_radius:
                    magnitude = -self.repulsion * (1.0 - distance / self.repulsion_radius)
                else:
                    magnitude = self.attraction * (1.0 - distance / self.interaction_radius)
                forces[index] += magnitude * direction
        return forces

    def step(self) -> np.ndarray:
        self._last_forces = self.forces()
        self.velocities = self.mobility * self._last_forces / (self.drag * self.masses[:, None])
        self.positions = (self.positions + self.timestep * self.velocities) % np.array([self.height, self.width])
        return self.positions.copy()

    def run(self, steps: int) -> None:
        for _ in range(steps):
            self.step()


def demo() -> None:
    world = ParticleWorld.seeded(seed=7)
    initial = world.positions.copy()
    world.run(200)
    assert np.isfinite(world.positions).all()
    assert np.all((world.positions >= 0) & (world.positions < np.array([world.height, world.width])))
    assert not np.array_equal(initial, world.positions)
    print(f"particle preflight passed: {len(world.positions)} particles, 200 steps")


if __name__ == "__main__":
    demo()
