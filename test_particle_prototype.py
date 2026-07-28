import unittest

import numpy as np

from particle_prototype import ParticleWorld


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


if __name__ == "__main__":
    unittest.main()
