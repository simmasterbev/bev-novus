import unittest

import numpy as np

from morrow import PatternCensus, World, ecology_metrics, evolvability_metrics
from experiments import run_condition


class WorldTests(unittest.TestCase):
    def test_total_mass_is_conserved(self) -> None:
        world = World.seeded(seed=7)
        world.resource_regrowth = world.waste_decay = 0.0
        initial = world.total_mass
        for _ in range(200):
            world.step()
        self.assertTrue(np.isclose(world.total_mass, initial, rtol=0.0, atol=1e-10))

    def test_renewable_ecology_tracks_environmental_delta(self) -> None:
        world = World.seeded(seed=7)
        initial = world.total_mass
        for _ in range(40):
            world.step()
        self.assertGreater(world.external_delta, 0.0)
        self.assertTrue(np.isclose(world.total_mass - initial, world.external_delta, atol=1e-9))

    def test_transport_is_conservative(self) -> None:
        world = World.seeded(seed=2)
        moved = world._transport(world.body, world._neighbor_mean(world.body))
        self.assertTrue(np.isclose(moved.sum(), world.body.sum(), rtol=0.0, atol=1e-10))

    def test_transport_stays_finite_for_extreme_affinity(self) -> None:
        world = World.seeded(seed=2)
        world.body[0, 0] = 1e12
        moved = world._transport(world.body, world._neighbor_mean(world.body), steering=5.0)
        self.assertTrue(np.isfinite(moved).all())

    def test_combined_transport_matches_individual_fields(self) -> None:
        world = World.seeded(seed=2)
        weights = world._transport_weights(world._neighbor_mean(world.body))
        masses = np.stack((world.body, world.trait_mass, world.mutation_mass))
        combined = world._apply_transport_fields(masses, weights)
        separate = np.stack([world._apply_transport(mass, weights) for mass in masses])
        self.assertTrue(np.allclose(combined, separate))

    def test_component_detection_wraps_at_world_edge(self) -> None:
        body = np.zeros((3, 3))
        body[0, 0] = body[0, 2] = body[1, 0] = body[1, 2] = 1.0
        world = World(body, np.zeros_like(body), np.zeros_like(body))
        self.assertEqual(world.localized_structures(threshold=0.5, min_cells=4), [4])

    def test_census_records_creation_persistence_and_destruction(self) -> None:
        body = np.zeros((5, 5)); body[1:3, 1:3] = 1.0
        world = World(body, np.zeros_like(body), np.zeros_like(body))
        census = PatternCensus()
        census.update(world.components(threshold=0.5))
        census.update(world.components(threshold=0.5))
        world.body[:] = 0.0
        census.update(world.components())
        self.assertEqual((census.created, census.persistent, census.destroyed), (1, 1, 1))

    def test_metabolism_outlasts_starvation_control(self) -> None:
        body = np.zeros((9, 9)); body[3:6, 3:6] = 1.0
        world = World(body, np.full_like(body, 2.0), np.zeros_like(body))
        active, starved = world.maintenance_probe(steps=30)
        self.assertGreater(active, starved)

    def test_perturbation_probe_remains_a_mass_conserving_comparison(self) -> None:
        world = World.seeded(seed=3)
        self.assertGreater(world.perturbation_probe(steps=20), 0.0)

    def test_reproduction_scaffold_conserves_body_and_copies_trait(self) -> None:
        body = np.zeros((24, 24)); body[10:13, 10:13] = 2.0
        world = World(body, np.ones_like(body), np.zeros_like(body), body * 0.7, rng=np.random.default_rng(4))
        census = PatternCensus(); census.update(world.components())
        before = world.body.sum()
        births = world.reproduce_scaffold(census, tick=0, mutation=0.0)
        self.assertEqual(len(births), 1)
        self.assertTrue(np.isclose(world.body.sum(), before, atol=1e-10))
        self.assertAlmostEqual(births[0].trait, 0.7)

    def test_intrinsic_seed_emission_inherits_a_mutable_description(self) -> None:
        body = np.zeros((24, 24)); body[10:13, 10:13] = 2.0
        world = World(body, np.ones_like(body), np.zeros_like(body), body * 0.7, body * 0.06, np.ones_like(body), rng=np.random.default_rng(5))
        before = world.total_mass
        births = world.intrinsic_reproduction()
        self.assertEqual(len(births), 1)
        self.assertTrue(np.isclose(world.total_mass, before, atol=1e-10))
        self.assertGreaterEqual(births[0].mutation_rate, 0.005)

    def test_viable_births_leave_the_pending_assessment_queue(self) -> None:
        body = np.zeros((24, 24)); body[10:13, 10:13] = 2.0
        world = World(body, np.ones_like(body), np.zeros_like(body), body * 0.7, body * 0.06, np.ones_like(body))
        birth = world.intrinsic_reproduction()[0]
        y, x = birth.center
        world.body[y, x] = 1.0
        world.assess_births(birth.tick + 30)
        self.assertTrue(birth.viable)
        self.assertEqual(world.pending_births, [])

    def test_ecology_and_evolvability_metrics_are_observable(self) -> None:
        world = World.seeded(seed=9)
        census = PatternCensus(); census.update(world.components())
        world.intrinsic_reproduction()
        for birth in world.births:
            birth.viable = True
        ecology, evolution = ecology_metrics(world, census), evolvability_metrics(world, census)
        self.assertGreater(ecology["resource_patchiness"], 0.0)
        self.assertGreaterEqual(evolution["mean_mutation_rate"], 0.0)

    def test_lineage_registration_assigns_child_and_generation(self) -> None:
        world = World.seeded(seed=8)
        census = PatternCensus(); census.update(world.components())
        world.intrinsic_reproduction()
        census.update(world.components())
        for birth in world.births:
            census.register_birth(birth, census.current)
        self.assertTrue(all(birth.child_id >= 0 and birth.generation >= 1 for birth in world.births))

    def test_control_condition_returns_measurable_result(self) -> None:
        result = run_condition("test", 1, steps=30, reproduce=False)
        self.assertEqual(result.label, "test")
        self.assertLess(result.mass_drift, 1e-8)

    def test_seeded_world_accepts_starting_configuration(self) -> None:
        world = World.seeded(seed=4, resource_patches=2, body_patches=1, source_scale=2.0,
                             resource_strength=1.4, body_strength=0.8)
        self.assertEqual(world.body.shape, (72, 96))
        self.assertTrue(np.isfinite(world.total_mass))

    def test_rule_parameters_survive_copy(self) -> None:
        world = World.seeded(seed=5)
        world.waste_inhibition, world.recycle_rate = 0.7, 0.04
        world.seed_fraction, world.mutation_scale = 0.3, 0.02
        clone = world.copy()
        self.assertEqual((clone.waste_inhibition, clone.recycle_rate, clone.seed_fraction, clone.mutation_scale),
                         (0.7, 0.04, 0.3, 0.02))


if __name__ == "__main__":
    unittest.main()
