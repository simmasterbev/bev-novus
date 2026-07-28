"""Bev Novus v1: conservative fields, ecology, and heritable seed emission."""

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
    parent_trait: float
    trait: float
    mutation_rate: float
    center: tuple[int, int]
    tick: int
    viable: bool = False
    child_id: int = 0
    generation: int = 0
    genotype: tuple[float, float] = (0.0, 0.0)


@dataclass
class PatternCensus:
    """Threshold-based accounting of patterns; IDs are observations, not organisms."""

    next_id: int = 1
    current: dict[int, Component] = field(default_factory=dict)
    ages: dict[int, int] = field(default_factory=dict)
    created: int = 0
    destroyed: int = 0
    generations: dict[int, int] = field(default_factory=dict)
    overlap_scores: list[float] = field(default_factory=list)
    ambiguous: int = 0
    merges: int = 0
    splits: int = 0

    def update(self, components: list[Component]) -> dict[int, Component]:
        prior_cells = {ident: component.cells for ident, component in self.current.items()}
        used, observed = set(), {}
        matches: dict[int, list[int]] = {ident: [] for ident in prior_cells}
        for component in components:
            all_overlaps = [(len(component.cells & cells), ident) for ident, cells in prior_cells.items() if len(component.cells & cells)]
            for _, ident in all_overlaps:
                matches[ident].append(len(observed))
            candidates = [(overlap, ident) for overlap, ident in all_overlaps if ident not in used]
            overlap, ident = max(candidates, default=(0, 0))
            if len(candidates) > 1 and sum(value == overlap for value, _ in candidates) > 1:
                self.ambiguous += 1
            self.overlap_scores.append(overlap / max(len(component.cells), 1))
            if overlap:
                used.add(ident)
                self.ages[ident] += 1
            else:
                ident = self.next_id
                self.next_id += 1
                self.ages[ident] = 1
                self.created += 1
                self.generations.setdefault(ident, 0)
            observed[ident] = component
            if len(all_overlaps) > 1:
                self.merges += 1
        self.splits += sum(len(ids) > 1 for ids in matches.values())
        self.destroyed += len(set(self.current) - set(observed))
        self.current = observed
        return observed

    @property
    def persistent(self) -> int:
        return sum(age > 1 for age in self.ages.values())

    @property
    def median_overlap(self) -> float:
        return float(np.median(self.overlap_scores)) if self.overlap_scores else 0.0

    def register_birth(self, birth: Birth, components: dict[int, Component]) -> None:
        if not components:
            return
        birth.child_id = min(components, key=lambda ident: (components[ident].center[0] - birth.center[0]) ** 2 + (components[ident].center[1] - birth.center[1]) ** 2)
        birth.generation = self.generations.get(birth.parent_id, 0) + 1
        self.generations[birth.child_id] = birth.generation


def ecology_metrics(world: "World", census: PatternCensus) -> dict[str, float]:
    traits = [component.trait for component in census.current.values()]
    niches = len(np.unique(np.floor(np.asarray(traits) * 4))) if traits else 0
    low_resource = world.body[world.resource < np.median(world.resource)]
    return {"resource_patchiness": float(world.resource.std()), "waste_patchiness": float(world.waste.std()),
            "coexisting_patterns": float(len(census.current)), "occupied_trait_niches": float(niches),
            "competition_pressure": float(low_resource.mean()) if low_resource.size else 0.0,
            "interference_pressure": float(np.mean(world.waste * world.body))}


def individuality_metrics(world: "World", census: PatternCensus) -> dict[str, float]:
    compactness, boundaries = [], []
    height, width = world.body.shape
    for component in census.current.values():
        perimeter = sum(1 for cell in component.cells for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))
                        if ((cell // width + dy) % height) * width + ((cell % width + dx) % width) not in component.cells)
        area = len(component.cells)
        compactness.append(4 * np.pi * area / max(perimeter * perimeter, 1))
        boundaries.append(perimeter / max(area, 1))
    return {"compactness": float(np.mean(compactness)) if compactness else 0.0,
            "boundary_ratio": float(np.mean(boundaries)) if boundaries else 0.0,
            "self_overlap": census.median_overlap,
            "merges": float(census.merges), "splits": float(census.splits),
            "ambiguous_identity": float(census.ambiguous)}


def evolvability_metrics(world: "World", census: PatternCensus) -> dict[str, float]:
    viable = [birth for birth in world.births if birth.viable]
    novelty = [abs(birth.trait - birth.parent_trait) for birth in viable]
    mutations = [birth.mutation_rate for birth in viable]
    traits = [component.trait for component in census.current.values()]
    return {"viable_births": float(len(viable)), "trait_diversity": float(np.std(traits)) if traits else 0.0,
            "mean_mutation_rate": float(np.mean(mutations)) if mutations else 0.0,
            "novel_viable_birth_fraction": float(np.mean(np.asarray(novelty) >= 0.01)) if novelty else 0.0}


def collective_metrics(world: "World", census: PatternCensus) -> dict[str, float]:
    multi_core = 0
    for component in census.current.values():
        peaks = sum(world.body[cell // world.body.shape[1], cell % world.body.shape[1]] >= world.body.max() * .8 for cell in component.cells)
        multi_core += peaks >= 2
    return {"multi_core_groups": float(multi_core), "group_persistence": float(census.persistent if multi_core else 0),
            "group_births": float(sum(birth.generation > 0 for birth in world.births))}


@dataclass
class World:
    body: np.ndarray
    resource: np.ndarray
    waste: np.ndarray
    trait_mass: np.ndarray | None = None
    mutation_mass: np.ndarray | None = None
    resource_source: np.ndarray | None = None
    metabolism_rate: float = 0.07
    body_yield: float = 0.72
    decay_rate: float = 0.012
    diffusion: float = 0.18
    steering: float = 2.0
    rng: np.random.Generator = field(default_factory=np.random.default_rng, repr=False)
    births: list[Birth] = field(default_factory=list)
    pending_births: list[Birth] = field(default_factory=list, repr=False)
    ticks: int = 0
    autonomous_reproduction: bool = True
    waste_inhibition: float = 0.45
    recycle_rate: float = 0.025
    seed_interval: int = 60
    seed_fraction: float = 0.22
    mutation_scale: float = 0.01
    resource_regrowth: float = 0.006
    resource_capacity: float = 1.0
    waste_decay: float = 0.002
    waste_diffusion: float = 0.12
    dormancy_threshold: float = 0.08
    dormancy_cost: float = 0.15
    complexity_pressure: float = 0.35
    external_delta: float = 0.0

    def __post_init__(self) -> None:
        if self.trait_mass is None:
            self.trait_mass = self.body * 0.5
        if self.mutation_mass is None:
            self.mutation_mass = self.body * 0.04
        if self.resource_source is None:
            self.resource_source = np.ones_like(self.body)

    @classmethod
    def seeded(cls, height: int = 72, width: int = 96, seed: int = 1, source_scale: float = 1.5,
               resource_patches: int = 7, body_patches: int = 5,
               resource_strength: float = 1.0, body_strength: float = 0.55) -> "World":
        rng = np.random.default_rng(seed)
        y, x = np.mgrid[:height, :width]
        resource = np.zeros((height, width), dtype=float)
        body = np.zeros_like(resource)
        traits = np.zeros_like(resource)
        mutability = np.zeros_like(resource)
        source = np.zeros_like(resource)
        for _ in range(resource_patches):
            cy, cx, radius = rng.uniform(0, height), rng.uniform(0, width), rng.uniform(6, 16)
            resource += resource_strength * np.exp(-((y - cy) ** 2 + (x - cx) ** 2) / radius**2)
            source += resource_strength * np.exp(-((y - cy) ** 2 + (x - cx) ** 2) / (radius * source_scale) ** 2)
        for _ in range(body_patches):
            cy, cx, radius = rng.uniform(0, height), rng.uniform(0, width), rng.uniform(2, 5)
            patch = body_strength * np.exp(-((y - cy) ** 2 + (x - cx) ** 2) / radius**2)
            body += patch
            traits += patch * rng.uniform(0.35, 0.65)
            mutability += patch * rng.uniform(0.02, 0.08)
        return cls(body, resource, np.zeros_like(resource), traits, mutability, source / source.max(), rng=rng)

    @property
    def total_mass(self) -> float:
        return float((self.body + self.resource + self.waste).sum())

    def trait_field(self) -> np.ndarray:
        return np.divide(self.trait_mass, self.body, out=np.full_like(self.body, 0.5), where=self.body > 1e-12)

    def mutation_field(self) -> np.ndarray:
        return np.divide(self.mutation_mass, self.body, out=np.full_like(self.body, 0.04), where=self.body > 1e-12)

    def step(self) -> None:
        """Local periodic transport and metabolism; matter and trait mass move together."""
        neighbor_body = self._neighbor_mean(self.body)
        affinity = neighbor_body + self.complexity_pressure * neighbor_body + 0.35 * self.resource - self.waste_inhibition * self.waste
        steering = 0.5 + 3.0 * self.trait_field()
        weights = self._transport_weights(affinity, steering)
        self.body, self.trait_mass, self.mutation_mass = self._apply_transport_fields(
            np.stack((self.body, self.trait_mass, self.mutation_mass)), weights)
        traits = self.trait_field()
        connectedness = np.divide(neighbor_body, self.body + neighbor_body, out=np.zeros_like(self.body), where=self.body + neighbor_body > 1e-12)
        intake = np.minimum(self.resource, self.metabolism_rate * (0.5 + traits) * self.body * self.resource * (1.0 + self.complexity_pressure * connectedness))
        self.resource -= intake
        growth = self.body_yield * intake
        self.body += growth
        self.trait_mass += traits * growth
        self.waste += (1.0 - self.body_yield) * intake
        dormant = self.body < self.dormancy_threshold
        decay = self.decay_rate * self.body * np.where(dormant, self.dormancy_cost, 1.0)
        self.body -= decay
        self.trait_mass -= traits * decay
        self.waste += decay
        regrown = self.resource_regrowth * self.resource_source * np.maximum(self.resource_capacity - self.resource, 0.0)
        self.resource += regrown
        waste_cleaned = self.waste_decay * self.waste
        self.waste -= waste_cleaned
        self.waste = (1.0 - self.waste_diffusion) * self.waste + self.waste_diffusion * self._neighbor_mean(self.waste)
        self.external_delta += float(regrown.sum() - waste_cleaned.sum())
        recycled = np.minimum(self.waste, self.recycle_rate * self.resource_source * self.waste)
        self.waste -= recycled
        self.resource += recycled
        self.ticks += 1
        if self.autonomous_reproduction and self.ticks % self.seed_interval == 0:
            self.intrinsic_reproduction()

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
        return self._seed_from_component(parent_id, parent, tick, mutation)

    def intrinsic_reproduction(self, division_mass: float = 8.0, min_resource: float = 0.12) -> list[Birth]:
        """Model-internal division rule: local body mass and resource permit seed emission."""
        candidates = [component for component in self.components() if component.mass >= division_mass and component.resource >= min_resource]
        if not candidates:
            return []
        return self._seed_from_component(0, max(candidates, key=lambda component: component.mass), self.ticks, None)

    def _seed_from_component(self, parent_id: int, parent: Component, tick: int, mutation: float | None) -> list[Birth]:
        height, width = self.body.shape
        direction = ((0, 12), (12, 0), (0, -12), (-12, 0))[len(self.births) % 4]
        target = (round(parent.center[0] + direction[0]) % height, round(parent.center[1] + direction[1]) % width)
        donor_y = np.array([cell // width for cell in parent.cells])
        donor_x = np.array([cell % width for cell in parent.cells])
        donation = self.body[donor_y, donor_x] * self.seed_fraction
        donated = float(donation.sum())
        if donated <= 0.0:
            return []
        parent_trait = float(self.trait_mass[donor_y, donor_x].sum() / self.body[donor_y, donor_x].sum())
        parent_mutation = float(np.clip(
            self.mutation_mass[donor_y, donor_x].sum() / self.body[donor_y, donor_x].sum(),
            0.005, 0.2,
        ))
        self.body[donor_y, donor_x] -= donation
        self.trait_mass[donor_y, donor_x] -= donation * parent_trait
        self.mutation_mass[donor_y, donor_x] -= donation * parent_mutation
        mutation = parent_mutation if mutation is None else float(np.clip(mutation, 0.0, 0.2))
        child_trait = float(np.clip(parent_trait + self.rng.normal(0.0, mutation), 0.0, 1.0))
        child_mutation = float(np.clip(parent_mutation + self.rng.normal(0.0, self.mutation_scale), 0.005, 0.2))
        kernel = np.array(((1.0, 2.0, 1.0), (2.0, 4.0, 2.0), (1.0, 2.0, 1.0))) / 16.0
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                y, x = (target[0] + dy) % height, (target[1] + dx) % width
                amount = donated * kernel[dy + 1, dx + 1]
                self.body[y, x] += amount
                self.trait_mass[y, x] += amount * child_trait
                self.mutation_mass[y, x] += amount * child_mutation
        birth = Birth(parent_id, parent_trait, child_trait, child_mutation, target, tick)
        self.births.append(birth)
        self.pending_births.append(birth)
        return [birth]

    def assess_births(self, tick: int, delay: int = 30, minimum_mass: float = 0.4) -> None:
        pending = []
        for birth in self.pending_births:
            if not birth.viable and tick - birth.tick >= delay:
                y, x = birth.center
                patch = self.body.take(range(y - 2, y + 3), axis=0, mode="wrap").take(range(x - 2, x + 3), axis=1, mode="wrap")
                birth.viable = float(patch.sum()) >= minimum_mass
            if not birth.viable:
                pending.append(birth)
        self.pending_births = pending

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
        return World(self.body.copy(), self.resource.copy(), self.waste.copy(), self.trait_mass.copy(), self.mutation_mass.copy(),
                     self.resource_source.copy(), self.metabolism_rate, self.body_yield, self.decay_rate, self.diffusion, self.steering,
                     np.random.default_rng(0), ticks=self.ticks, autonomous_reproduction=self.autonomous_reproduction,
                     waste_inhibition=self.waste_inhibition, recycle_rate=self.recycle_rate, seed_interval=self.seed_interval,
                     seed_fraction=self.seed_fraction, mutation_scale=self.mutation_scale,
                     resource_regrowth=self.resource_regrowth, resource_capacity=self.resource_capacity,
                     waste_decay=self.waste_decay, waste_diffusion=self.waste_diffusion,
                     dormancy_threshold=self.dormancy_threshold, dormancy_cost=self.dormancy_cost,
                     complexity_pressure=self.complexity_pressure, external_delta=self.external_delta)

    def _neighbor_mean(self, field: np.ndarray) -> np.ndarray:
        result = field.copy()
        result[1:] += field[:-1]; result[0] += field[-1]
        result[:-1] += field[1:]; result[-1] += field[0]
        result[:, 1:] += field[:, :-1]; result[:, 0] += field[:, -1]
        result[:, :-1] += field[:, 1:]; result[:, -1] += field[:, 0]
        return result / 5.0

    def _transport(self, mass: np.ndarray, affinity: np.ndarray, steering: np.ndarray | float | None = None) -> np.ndarray:
        return self._apply_transport(mass, self._transport_weights(affinity, steering))

    def _transport_weights(self, affinity: np.ndarray, steering: np.ndarray | float | None = None) -> np.ndarray:
        steering = self.steering if steering is None else steering
        scores = np.empty((5, *affinity.shape), dtype=affinity.dtype)
        scores[0] = 0.0
        scores[1, :-1] = affinity[1:] - affinity[:-1]; scores[1, -1] = affinity[0] - affinity[-1]
        scores[2, 1:] = affinity[:-1] - affinity[1:]; scores[2, 0] = affinity[-1] - affinity[0]
        scores[3, :, :-1] = affinity[:, 1:] - affinity[:, :-1]; scores[3, :, -1] = affinity[:, 0] - affinity[:, -1]
        scores[4, :, 1:] = affinity[:, :-1] - affinity[:, 1:]; scores[4, :, 0] = affinity[:, -1] - affinity[:, 0]
        scores[1:] *= steering
        scores -= scores.max(axis=0, keepdims=True)
        np.clip(scores, -60.0, 0.0, out=scores)
        np.exp(scores, out=scores)
        scores *= (1.0 - self.diffusion) / scores.sum(axis=0, keepdims=True)
        scores += self.diffusion / 5.0
        return scores

    def _apply_transport(self, mass: np.ndarray, weights: np.ndarray) -> np.ndarray:
        directions = ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))
        return sum(np.roll(mass * weight, direction, axis=(0, 1)) for weight, direction in zip(weights, directions))

    def _apply_transport_fields(self, masses: np.ndarray, weights: np.ndarray) -> np.ndarray:
        result = masses * weights[0]
        result[:, 1:] += masses[:, :-1] * weights[1, :-1]; result[:, 0] += masses[:, -1] * weights[1, -1]
        result[:, :-1] += masses[:, 1:] * weights[2, 1:]; result[:, -1] += masses[:, 0] * weights[2, 0]
        result[:, :, 1:] += masses[:, :, :-1] * weights[3, :, :-1]; result[:, :, 0] += masses[:, :, -1] * weights[3, :, -1]
        result[:, :, :-1] += masses[:, :, 1:] * weights[4, :, 1:]; result[:, :, -1] += masses[:, :, 0] * weights[4, :, 0]
        return result

    def write_ppm(self, path: Path) -> None:
        def scale(field: np.ndarray) -> np.ndarray:
            return np.clip(field / max(float(np.quantile(field, 0.995)), 1e-9), 0.0, 1.0)
        pixels = (255 * np.dstack((scale(self.waste), scale(self.body), scale(self.resource)))).astype(np.uint8)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as stream:
            stream.write(f"P6\n{pixels.shape[1]} {pixels.shape[0]}\n255\n".encode())
            stream.write(pixels.tobytes())


def reproduction_preflight(seeds: tuple[int, ...] = (1, 2, 3)) -> dict[str, float | int]:
    """Run a cheap GUI safety check for invalid inherited mutation scales."""
    births = []
    for seed in seeds:
        world = World.seeded(seed=seed, source_scale=2.5, resource_strength=2.0, body_strength=1.1)
        components = world.components()
        if not components:
            raise RuntimeError(f"seed {seed} produced no reproduction candidate")
        parent = components[0]
        width = world.body.shape[1]
        ys = np.asarray([cell // width for cell in parent.cells])
        xs = np.asarray([cell % width for cell in parent.cells])
        world.mutation_mass[ys, xs] = -1e-8
        emitted = world.intrinsic_reproduction()
        if not emitted:
            raise RuntimeError(f"seed {seed} emitted no birth during mutation preflight")
        births.extend(emitted)
    rates = [birth.mutation_rate for birth in births]
    if not all(np.isfinite(rates)) or min(rates) < 0.005 or max(rates) > 0.2:
        raise RuntimeError("preflight produced an invalid child mutation rate")
    return {"seeds": len(seeds), "births": len(births), "minimum_mutation_rate": float(min(rates))}


def run(steps: int, every: int, output: Path, seed: int, probe: bool = False, config: dict | None = None) -> World:
    config = config or {}
    world, census = World.seeded(seed=seed, **{key: config[key] for key in (
        "source_scale", "resource_patches", "body_patches", "resource_strength", "body_strength"
    ) if key in config}), PatternCensus()
    for key in ("metabolism_rate", "body_yield", "decay_rate", "diffusion", "steering", "waste_inhibition",
                "recycle_rate", "seed_interval", "seed_fraction", "mutation_scale"):
        if key in config:
            setattr(world, key, config[key])
    for key in ("resource_regrowth", "resource_capacity", "waste_decay", "waste_diffusion", "dormancy_threshold", "dormancy_cost", "complexity_pressure"):
        if key in config:
            setattr(world, key, config[key])
    census.update(world.components())
    baseline = world.total_mass
    for tick in range(steps + 1):
        if tick % every == 0:
            world.write_ppm(output / f"frame-{tick:05d}.ppm")
        if tick < steps:
            prior = dict(census.current)
            prior_births = len(world.births)
            world.step()
            census.update(world.components())
            for birth in world.births[prior_births:]:
                if prior:
                    birth.parent_id = min(prior, key=lambda ident: abs(prior[ident].trait - birth.parent_trait))
            world.assess_births(tick)
    active, starved = world.maintenance_probe() if probe else (float("nan"), float("nan"))
    repair = world.perturbation_probe() if probe else float("nan")
    viable = sum(birth.viable for birth in world.births)
    ecology, evolution = ecology_metrics(world, census), evolvability_metrics(world, census)
    print(f"steps={steps} mass={world.total_mass:.9f} balance={abs(world.total_mass-baseline-world.external_delta):.3e} "
          f"live={len(census.current)} created={census.created} destroyed={census.destroyed} "
          f"births={len(world.births)} viable={viable} maintenance={active:.3f}/{starved:.3f} repair={repair:.3f} "
          f"niches={ecology['occupied_trait_niches']:.0f} novelty={evolution['novel_viable_birth_fraction']:.2f}")
    return world


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Bev Novus v1.")
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--every", type=int, default=100)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", type=Path, default=Path("output"))
    parser.add_argument("--probe", action="store_true", help="run the maintenance-versus-starvation comparison")
    parser.add_argument("--metabolism-rate", type=float, default=0.07)
    parser.add_argument("--body-yield", type=float, default=0.72)
    parser.add_argument("--decay-rate", type=float, default=0.012)
    parser.add_argument("--waste-inhibition", type=float, default=0.45)
    parser.add_argument("--recycle-rate", type=float, default=0.025)
    parser.add_argument("--diffusion", type=float, default=0.18)
    parser.add_argument("--steering", type=float, default=2.0)
    parser.add_argument("--seed-interval", type=int, default=60)
    parser.add_argument("--seed-fraction", type=float, default=0.22)
    parser.add_argument("--mutation-scale", type=float, default=0.01)
    parser.add_argument("--resource-patches", type=int, default=7)
    parser.add_argument("--body-patches", type=int, default=5)
    parser.add_argument("--resource-strength", type=float, default=1.0)
    parser.add_argument("--body-strength", type=float, default=0.55)
    parser.add_argument("--source-scale", type=float, default=1.5)
    parser.add_argument("--resource-regrowth", type=float, default=0.006)
    parser.add_argument("--resource-capacity", type=float, default=1.0)
    parser.add_argument("--waste-decay", type=float, default=0.002)
    parser.add_argument("--waste-diffusion", type=float, default=0.12)
    parser.add_argument("--dormancy-threshold", type=float, default=0.08)
    parser.add_argument("--dormancy-cost", type=float, default=0.15)
    parser.add_argument("--complexity-pressure", type=float, default=0.35)
    args = parser.parse_args()
    if args.steps < 0 or args.every < 1:
        parser.error("--steps must be non-negative and --every must be at least 1")
    run(args.steps, args.every, args.out, args.seed, args.probe, vars(args))


if __name__ == "__main__":
    main()
