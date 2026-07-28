import unittest

import numpy as np

from particle_prototype import HybridParticleWorld, ParticleWorld, stability_report


class ParticleWorldTests(unittest.TestCase):
    def test_neighbor_lookup_wraps_at_boundary(self) -> None:
        world = ParticleWorld(np.array([[4.0, 0.5], [4.0, 95.5]]), width=96, height=72)
        nearby = world._nearby(0, world._bins())
        self.assertEqual(nearby, [1])

    def test_short_range_repulsion_separates_particles(self) -> None:
        world = ParticleWorld(np.array([[36.0, 40.0], [36.0, 41.0]]), attraction=0.0, repulsion=2.0)
        before = np.linalg.norm(world.positions[1] - world.positions[0])
        world.step()
        after = np.linalg.norm(world.positions[1] - world.positions[0])
        self.assertGreater(after, before)

    def test_medium_range_attraction_reduces_distance(self) -> None:
        world = ParticleWorld(np.array([[36.0, 40.0], [36.0, 44.0]]), attraction=1.0, repulsion=0.0)
        before = np.linalg.norm(world.positions[1] - world.positions[0])
        world.step()
        after = np.linalg.norm(world.positions[1] - world.positions[0])
        self.assertLess(after, before)

    def test_seeded_runs_are_deterministic_and_bounded(self) -> None:
        left, right = ParticleWorld.seeded(seed=4), ParticleWorld.seeded(seed=4)
        left.run(100); right.run(100)
        self.assertTrue(np.array_equal(left.positions, right.positions))
        self.assertTrue(np.isfinite(left.positions).all())
        self.assertTrue(np.all((left.positions >= 0) & (left.positions < np.array([left.height, left.width]))))

    def test_stability_report_passes_timestep_sweep(self) -> None:
        report = stability_report(seeds=(1, 2), steps=100)
        self.assertEqual(len(report), 6)
        self.assertTrue(all(row["finite"] and row["bounded"] for row in report))

    def test_hybrid_world_conserves_body_resource_waste_without_external_terms(self) -> None:
        particle = ParticleWorld(np.array([[12.0, 12.0], [12.0, 13.0]]), width=24, height=24,
                                 attraction=0.0, repulsion=0.0)
        resource = np.ones((24, 24))
        hybrid = HybridParticleWorld(particle, resource, np.zeros_like(resource),
                                     source=np.zeros_like(resource), resource_regrowth=0.0, waste_decay=0.0)
        before = hybrid.total_mass
        hybrid.run(20)
        self.assertTrue(np.isclose(hybrid.total_mass, before, atol=1e-10))
        self.assertGreater(hybrid.waste.sum(), 0.0)
        self.assertTrue(np.isfinite(hybrid.particle.positions).all())

    def test_hybrid_world_responds_to_resource_gradient(self) -> None:
        particle = ParticleWorld(np.array([[12.0, 11.0]]), width=24, height=24,
                                 attraction=0.0, repulsion=0.0, mobility=1.0, timestep=0.1)
        resource = np.zeros((24, 24)); resource[:, 12:] = 2.0
        hybrid = HybridParticleWorld(particle, resource, np.zeros_like(resource),
                                     source=np.zeros_like(resource), metabolism=0.0,
                                     resource_regrowth=0.0, resource_taxis=1.0)
        before = hybrid.particle.positions[0, 1]
        hybrid.step()
        self.assertGreater(hybrid.particle.positions[0, 1], before)

    def test_seeded_hybrid_world_is_reproducible(self) -> None:
        left, right = HybridParticleWorld.seeded(seed=8), HybridParticleWorld.seeded(seed=8)
        left.run(20); right.run(20)
        self.assertTrue(np.array_equal(left.particle.positions, right.particle.positions))
        self.assertTrue(np.array_equal(left.resource, right.resource))


if __name__ == "__main__":
    unittest.main()
