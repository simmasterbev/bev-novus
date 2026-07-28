"""Minimal overdamped particle mechanics prototype for Bev Novus Phase 1."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class ParticleWorld:
    """Periodic, short-range particle world with overdamped motion."""

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

    def _advance(self, forces: np.ndarray) -> np.ndarray:
        self._last_forces = forces
        self.velocities = self.mobility * self._last_forces / (self.drag * self.masses[:, None])
        self.positions = (self.positions + self.timestep * self.velocities) % np.array([self.height, self.width])
        return self.positions.copy()

    def step(self, external_forces: np.ndarray | None = None) -> np.ndarray:
        forces = self.forces()
        if external_forces is not None:
            external_forces = np.asarray(external_forces, dtype=float)
            if external_forces.shape != forces.shape:
                raise ValueError("external_forces must match positions")
            forces += external_forces
        return self._advance(forces)

    def run(self, steps: int) -> None:
        for _ in range(steps):
            self.step()


@dataclass
class HybridParticleWorld:
    """Phase 1 hybrid: particles for body matter, grids for resource and waste."""

    particle: ParticleWorld
    resource: np.ndarray
    waste: np.ndarray
    source: np.ndarray | None = None
    metabolism: float = 0.02
    body_yield: float = 0.72
    resource_regrowth: float = 0.006
    resource_capacity: float = 1.0
    waste_decay: float = 0.002
    resource_taxis: float = 0.15
    waste_avoidance: float = 0.15

    @classmethod
    def seeded(cls, seed: int = 1, count: int = 32, width: int = 96, height: int = 72) -> "HybridParticleWorld":
        rng = np.random.default_rng(seed)
        y, x = np.mgrid[:height, :width]
        resource = np.zeros((height, width), dtype=float)
        source = np.zeros_like(resource)
        for _ in range(5):
            cy, cx, radius = rng.uniform(0, height), rng.uniform(0, width), rng.uniform(6, 14)
            patch = np.exp(-((y - cy) ** 2 + (x - cx) ** 2) / radius**2)
            resource += patch
            source += patch
        positions = np.column_stack((rng.uniform(0, height, count), rng.uniform(0, width, count)))
        return cls(ParticleWorld(positions, width=width, height=height), resource, np.zeros_like(resource), source)

    def __post_init__(self) -> None:
        shape = (int(self.particle.height), int(self.particle.width))
        self.resource = np.asarray(self.resource, dtype=float).copy()
        self.waste = np.asarray(self.waste, dtype=float).copy()
        self.source = np.ones(shape, dtype=float) if self.source is None else np.asarray(self.source, dtype=float).copy()
        if self.resource.shape != shape or self.waste.shape != shape or self.source.shape != shape:
            raise ValueError("resource, waste, and source must match the world dimensions")
        if not 0.0 <= self.body_yield <= 1.0:
            raise ValueError("body_yield must be between 0 and 1")

    @property
    def total_mass(self) -> float:
        return float(self.particle.masses.sum() + self.resource.sum() + self.waste.sum())

    def _indices(self) -> tuple[np.ndarray, np.ndarray]:
        y = np.rint(self.particle.positions[:, 0]).astype(int) % self.resource.shape[0]
        x = np.rint(self.particle.positions[:, 1]).astype(int) % self.resource.shape[1]
        return y, x

    def _field_forces(self) -> np.ndarray:
        resource_y = (np.roll(self.resource, -1, axis=0) - np.roll(self.resource, 1, axis=0)) / 2.0
        resource_x = (np.roll(self.resource, -1, axis=1) - np.roll(self.resource, 1, axis=1)) / 2.0
        waste_y = (np.roll(self.waste, -1, axis=0) - np.roll(self.waste, 1, axis=0)) / 2.0
        waste_x = (np.roll(self.waste, -1, axis=1) - np.roll(self.waste, 1, axis=1)) / 2.0
        y, x = self._indices()
        return np.column_stack((self.resource_taxis * resource_y[y, x] - self.waste_avoidance * waste_y[y, x],
                                self.resource_taxis * resource_x[y, x] - self.waste_avoidance * waste_x[y, x]))

    def step(self) -> None:
        self.resource += self.resource_regrowth * self.source * np.maximum(self.resource_capacity - self.resource, 0.0)
        self.resource = np.maximum(self.resource, 0.0)
        self.particle.step(self._field_forces())
        y, x = self._indices()
        for index, (row, column) in enumerate(zip(y, x)):
            available = self.resource[row, column]
            intake = min(available, self.metabolism * self.particle.masses[index] * max(available, 0.0))
            self.resource[row, column] -= intake
            self.particle.masses[index] += self.body_yield * intake
            self.waste[row, column] += (1.0 - self.body_yield) * intake
        self.waste *= max(0.0, 1.0 - self.waste_decay)

    def run(self, steps: int) -> None:
        for _ in range(steps):
            self.step()


def stability_report(seeds: tuple[int, ...] = (1, 2, 3), steps: int = 500) -> list[dict[str, float | int | bool]]:
    """Run the small fixed-seed timestep sweep used before hybrid integration."""
    report = []
    for timestep in (0.02, 0.05, 0.1):
        for seed in seeds:
            world = ParticleWorld.seeded(seed=seed)
            world.timestep = timestep
            world.run(steps)
            report.append({"seed": seed, "timestep": timestep, "steps": steps,
                           "finite": bool(np.isfinite(world.positions).all()),
                           "bounded": bool(np.all((world.positions >= 0) &
                                                  (world.positions < np.array([world.height, world.width])))),
                           "max_speed": float(np.linalg.norm(world.velocities, axis=1).max())})
    return report


def demo() -> None:
    world = ParticleWorld.seeded(seed=7)
    initial = world.positions.copy()
    world.run(200)
    assert np.isfinite(world.positions).all()
    assert np.all((world.positions >= 0) & (world.positions < np.array([world.height, world.width])))
    assert not np.array_equal(initial, world.positions)
    assert all(row["finite"] and row["bounded"] for row in stability_report())
    print(f"particle preflight passed: {len(world.positions)} particles, 200 steps; timestep sweep passed")


if __name__ == "__main__":
    demo()
