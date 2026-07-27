import unittest

import numpy as np

from morrow import World


class WorldTests(unittest.TestCase):
    def test_total_mass_is_conserved(self) -> None:
        world = World.seeded(seed=7)
        initial = world.total_mass
        for _ in range(200):
            world.step()
        self.assertTrue(np.isclose(world.total_mass, initial, rtol=0.0, atol=1e-10))

    def test_transport_is_conservative(self) -> None:
        world = World.seeded(seed=2)
        moved = world._transport(world.body, world._neighbor_mean(world.body))
        self.assertTrue(np.isclose(moved.sum(), world.body.sum(), rtol=0.0, atol=1e-10))
