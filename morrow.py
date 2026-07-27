"""Morrow 0.4: conservative fields, pattern census, and a reproduction scaffold."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class Component:
    cells: frozenset[int]
    mass: float
    trait: float
    resource: float
    center: tuple[float, float]


@dataclass
class Birth:
    parent_id: int
    trait: float
    center: tuple[int, int]
    tick: int
    viable: bool = False


@dataclass
class PatternCensus:
    """Threshold-based accounting of patterns; IDs are observations, not organisms."""

    next_id: int = 1
    current: dict[int, Component] = field(default_factory=dict)
    ages: dict[int, int] = field(default_factory=dict)
    created: int = 0
    destroyed: int = 0

    def update(self, components: list[Component]) -> dict[int, Component]:
        prior_cells = {ident: component.cells for ident, component in self.current.items()}
        used, observed = set(), {}
        for component in components:
            candidates = [(len(component.cells & cells), ident) for ident, cells in prior_cells.items() if ident not in used]
            overlap, ident = max(candidates, default=(0, 0))
            if overlap:
                used.add(ident)
                self.ages[ident] += 1
            else:
                ident = self.next_id
                self.next_id += 1
                self.ages[ident] = 1
                self.created += 1
            observed[ident] = component
        self.destroyed += len(set(self.current) - set(observed))
        self.current = observed
        return observed

    @property
    def persistent(self) -> int:
        return sum(age > 1 for age in self.ages.values())


@dataclass
class World:
    body: np.ndarray
    resource: np.ndarray
    waste: np.ndarray
    trait_mass: np.ndarray | None = None
    metabolism_rate: float = 0.07
    body_yield: float = 0.72
    decay_rate: float = 0.012
    diffusion: float = 0.18
    steering: float = 2.0
    rng: np.random.Generator = field(default_factory=np.random.default_rng, repr=False)
    births: list[Birth] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.trait_mass is None:
            self.trait_mass = self.body * 0.5

    @classmethod
    def seeded(cls, height: int = 72, width: int = 96, seed: int = 1) -> "World":
        rng = np.random.default_rng(seed)
        y, x = np.mgrid[:height, :width]
        resource = np.zeros((height, width), dtype=float)
        body = np.zeros_like(resource)
        traits = np.zeros_like(resource)
        for _ in range(7):
            cy, cx, radius = rng.uniform(0, height), rng.uniform(0, width), rng.uniform(6, 16)
            resource += np.exp(-((y - cy) ** 2 + (x - cx) ** 2) / radius**2)
        for _ in range(5):
            cy, cx, radius = rng.uniform(0, height), rng.uniform(0, width), rng.uniform(2, 5)
            patch = 0.55 * np.exp(-((y - cy) ** 2 + (x - cx) ** 2) / radius**2)
            body += patch
            traits += patch * rng.uniform(0.35, 0.65)
        return cls(body, resource, np.zeros_like(resource), traits, rng=rng)

    @property
    def total_mass(self) -> float:
        return float((self.body + self.resource + self.waste).sum())

    def trait_field(self) -> np.ndarray:
        return np.divide(self.trait_mass, self.body, out=np.full_like(self.body, 0.5), where=self.body > 1e-12)

    def step(self) -> None:
        """Local periodic transport and metabolism; matter and trait mass move together."""
        affinity = self._neighbor_mean(self.body) + 0.35 * self.resource - 0.45 * self.waste
        self.body = self._transport(self.body, affinity)
        self.trait_mass = self._transport(self.trait_mass, affinity)
        traits = self.trait_field()
        intake = np.minimum(self.resource, self.metabolism_rate * (0.5 + traits) * self.body * self.resource)
        self.resource -= intake
        growth = self.body_yield * intake
        self.body += growth
        self.trait_mass += traits * growth
        self.waste += (1.0 - self.body_yield) * intake
        decay = self.decay_rate * self.body
        self.body -= decay
        self.trait_mass -= traits * decay
        self.waste += decay

    def components(self, threshold: float = 0.25, min_cells: int = 4) -> list[Component]:
        """Describe thresholded body components, preserving periodic edge connectivity."""
        if not 0.0 < threshold <= 1.0 or min_cells < 1:
            raise ValueError("threshold must be in (0, 1] and min_cells must be positive")
        peak = self.body.max()
        if peak <= 0.0:
            return []
        mask, seen = self.body >= threshold * peak, np.zeros_like(self.body, dtype=bool)
        height, width = mask.shape
        found = []
        for start_y, start_x in zip(*np.nonzero(mask & ~seen)):
            if seen[start_y, start_x]:
                continue
            stack, cells = [(start_y, start_x)], []
            seen[start_y, start_x] = True
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = (y + dy) % height, (x + dx) % width
                    if mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            if len(cells) >= min_cells:
                ys, xs = np.array(cells).T
                masses = self.body[ys, xs]
                mass = float(masses.sum())
                found.append(Component(frozenset(y * width + x for y, x in cells), mass,
                    float(self.trait_mass[ys, xs].sum() / mass), float(self.resource[ys, xs].mean()),
                    (float(np.average(ys, weights=masses)), float(np.average(xs, weights=masses)))))
        return sorted(found, key=lambda component: component.mass, reverse=True)

    def localized_structures(self, threshold: float = 0.25, min_cells: int = 4) -> list[int]:
        return [len(component.cells) for component in self.components(threshold, min_cells)]

    def reproduce_scaffold(self, census: PatternCensus, tick: int, division_mass: float = 8.0,
                           min_resource: float = 0.12, mutation: float = 0.04) -> list[Birth]:
        """External bridge: move parent mass into a mutated local offspring seed."""
        candidates = [(ident, component) for ident, component in census.current.items()
                      if component.mass >= division_mass and component.resource >= min_resource]
        if not candidates:
            return []
        parent_id, parent = max(candidates, key=lambda item: item[1].mass)
        height, width = self.body.shape
        direction = ((0, 12), (12, 0), (0, -12), (-12, 0))[len(self.births) % 4]
        target = (round(parent.center[0] + direction[0]) % height, round(parent.center[1] + direction[1]) % width)
        donor_y = np.array([cell // width for cell in parent.cells])
        donor_x = np.array([cell % width for cell in parent.cells])
        donation = self.body[donor_y, donor_x] * 0.22
        donated = float(donation.sum())
        if donated <= 0.0:
            return []
        parent_trait = float(self.trait_mass[donor_y, donor_x].sum() / self.body[donor_y, donor_x].sum())
        self.body[donor_y, donor_x] -= donation
        self.trait_mass[donor_y, donor_x] -= donation * parent_trait
        child_trait = float(np.clip(parent_trait + self.rng.normal(0.0, mutation), 0.0, 1.0))
        kernel = np.array(((1.0, 2.0, 1.0), (2.0, 4.0, 2.0), (1.0, 2.0, 1.0))) / 16.0
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                y, x = (target[0] + dy) % height, (target[1] + dx) % width
                amount = donated * kernel[dy + 1, dx + 1]
                self.body[y, x] += amount
                self.trait_mass[y, x] += amount * child_trait
        birth = Birth(parent_id, child_trait, target, tick)
        self.births.append(birth)
        return [birth]

    def assess_births(self, tick: int, delay: int = 30, minimum_mass: float = 0.4) -> None:
        for birth in self.births:
            if not birth.viable and tick - birth.tick >= delay:
                y, x = birth.center
                patch = self.body.take(range(y - 2, y + 3), axis=0, mode="wrap").take(range(x - 2, x + 3), axis=1, mode="wrap")
                birth.viable = float(patch.sum()) >= minimum_mass

    def maintenance_probe(self, steps: int = 120) -> tuple[float, float]:
        """Compare final body mass with metabolism enabled versus switched off."""
        active = self.copy()
        starved = self.copy()
        starved.metabolism_rate = 0.0
        initial = active.body.sum()
        for _ in range(steps):
            active.step()
            starved.step()
        return float(active.body.sum() / initial), float(starved.body.sum() / initial)

    def perturbation_probe(self, steps: int = 80) -> float:
        """Damage a local body patch and report its final mass relative to an undamaged control."""
        control, damaged = self.copy(), self.copy()
        source = np.unravel_index(np.argmax(damaged.body), damaged.body.shape)
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                y, x = (source[0] + dy) % damaged.body.shape[0], (source[1] + dx) % damaged.body.shape[1]
                loss = damaged.body[y, x] * 0.5
                trait = damaged.trait_field()[y, x]
                damaged.body[y, x] -= loss
                damaged.trait_mass[y, x] -= loss * trait
                damaged.waste[y, x] += loss
        for _ in range(steps):
            control.step()
            damaged.step()
        return float(damaged.body.sum() / max(control.body.sum(), 1e-12))

    def copy(self) -> "World":
        return World(self.body.copy(), self.resource.copy(), self.waste.copy(), self.trait_mass.copy(), self.metabolism_rate,
                     self.body_yield, self.decay_rate, self.diffusion, self.steering, np.random.default_rng(0))

    def _neighbor_mean(self, field: np.ndarray) -> np.ndarray:
        return (field + np.roll(field, 1, 0) + np.roll(field, -1, 0) + np.roll(field, 1, 1) + np.roll(field, -1, 1)) / 5.0

    def _transport(self, mass: np.ndarray, affinity: np.ndarray) -> np.ndarray:
        directions = ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))
        logits = [np.ones_like(affinity)] + [np.exp(self.steering * (np.roll(affinity, (-dy, -dx), axis=(0, 1)) - affinity)) for dy, dx in directions[1:]]
        weights = np.stack(logits)
        weights = (1.0 - self.diffusion) * weights / weights.sum(axis=0, keepdims=True) + self.diffusion / 5.0
        return sum(np.roll(mass * weight, direction, axis=(0, 1)) for weight, direction in zip(weights, directions))

    def write_ppm(self, path: Path) -> None:
        def scale(field: np.ndarray) -> np.ndarray:
            return np.clip(field / max(float(np.quantile(field, 0.995)), 1e-9), 0.0, 1.0)
        pixels = (255 * np.dstack((scale(self.waste), scale(self.body), scale(self.resource)))).astype(np.uint8)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as stream:
            stream.write(f"P6\n{pixels.shape[1]} {pixels.shape[0]}\n255\n".encode())
            stream.write(pixels.tobytes())


def run(steps: int, every: int, output: Path, seed: int, reproduce: bool = False, probe: bool = False) -> World:
    world, census = World.seeded(seed=seed), PatternCensus()
    census.update(world.components())
    baseline = world.total_mass
    for tick in range(steps + 1):
        if tick % every == 0:
            world.write_ppm(output / f"frame-{tick:05d}.ppm")
        if tick < steps:
            world.step()
            census.update(world.components())
            if reproduce and tick % 60 == 0:
                world.reproduce_scaffold(census, tick)
            world.assess_births(tick)
    active, starved = world.maintenance_probe() if probe else (float("nan"), float("nan"))
    repair = world.perturbation_probe() if probe else float("nan")
    viable = sum(birth.viable for birth in world.births)
    print(f"steps={steps} mass={world.total_mass:.9f} drift={abs(world.total_mass-baseline):.3e} "
          f"live={len(census.current)} created={census.created} destroyed={census.destroyed} "
          f"births={len(world.births)} viable={viable} maintenance={active:.3f}/{starved:.3f} repair={repair:.3f}")
    return world


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Morrow milestones 1-4.")
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--every", type=int, default=100)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", type=Path, default=Path("output"))
    parser.add_argument("--reproduce", action="store_true", help="enable the explicitly external reproduction scaffold")
    parser.add_argument("--probe", action="store_true", help="run the maintenance-versus-starvation comparison")
    args = parser.parse_args()
    if args.steps < 0 or args.every < 1:
        parser.error("--steps must be non-negative and --every must be at least 1")
    run(args.steps, args.every, args.out, args.seed, args.reproduce, args.probe)


if __name__ == "__main__":
    main()
