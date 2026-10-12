
"""
Unit tests for the production-ready consistent hashing implementation.

Expected layout:
    examples/10_production_ready_consistent_hashing.py
    tests/test_consistent_hashing.py

Run from the repository root:
    python -m unittest discover -s tests -v

The implementation filename starts with a number, so importlib loads it.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from collections import Counter

ROOT_DIR = Path(__file__).resolve().parents[1]
IMPLEMENTATION_PATH = ROOT_DIR / "examples" / "10_production_ready_consistent_hashing.py"

if not IMPLEMENTATION_PATH.exists():
    raise FileNotFoundError(
        f"Implementation not found: {IMPLEMENTATION_PATH}. "
        "Place this test at tests/test_consistent_hashing.py and the implementation "
        "at examples/10_production_ready_consistent_hashing.py."
    )

SPEC = importlib.util.spec_from_file_location("production_ready_consistent_hashing", IMPLEMENTATION_PATH)
if SPEC is None or SPEC.loader is None:
    raise ImportError(f"Could not load implementation from {IMPLEMENTATION_PATH}")

consistent_hashing = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = consistent_hashing
SPEC.loader.exec_module(consistent_hashing)

ConsistentHashRing = consistent_hashing.ConsistentHashRing
stable_hash = consistent_hashing.stable_hash


class TestStableHash(unittest.TestCase):
    def test_same_input_produces_same_hash(self):
        self.assertEqual(stable_hash("customer-123"), stable_hash("customer-123"))

    def test_different_inputs_usually_produce_different_hashes(self):
        self.assertNotEqual(stable_hash("customer-123"), stable_hash("customer-456"))

    def test_hash_is_a_non_negative_integer(self):
        value = stable_hash("any-key")
        self.assertIsInstance(value, int)
        self.assertGreaterEqual(value, 0)


class TestConsistentHashRing(unittest.TestCase):
    def setUp(self):
        self.ring = ConsistentHashRing(virtual_nodes=50)

    def test_empty_ring_has_no_servers(self):
        self.assertEqual(self.ring.servers, [])
        self.assertEqual(self.ring.ring_size, 0)

    def test_lookup_on_empty_ring_raises(self):
        with self.assertRaises((ValueError, RuntimeError)):
            self.ring.get_server("customer-123")

    def test_single_server_receives_every_key(self):
        self.ring.add_server("cache-a")
        for key in ("alpha", "beta", "gamma", "customer-123"):
            self.assertEqual(self.ring.get_server(key), "cache-a")

    def test_multiple_servers_and_ring_size(self):
        for server in ("cache-a", "cache-b", "cache-c"):
            self.ring.add_server(server)
        self.assertEqual(set(self.ring.servers), {"cache-a", "cache-b", "cache-c"})
        self.assertEqual(self.ring.ring_size, 150)

    def test_same_key_is_stable_without_ring_changes(self):
        for server in ("cache-a", "cache-b", "cache-c"):
            self.ring.add_server(server)
        expected = self.ring.get_server("customer-123")
        for _ in range(10):
            self.assertEqual(self.ring.get_server("customer-123"), expected)

    def test_adding_duplicate_server_does_not_duplicate_ring_entries(self):
        self.ring.add_server("cache-a")
        size_before = self.ring.ring_size
        self.ring.add_server("cache-a")
        self.assertEqual(self.ring.ring_size, size_before)
        self.assertEqual(self.ring.servers.count("cache-a"), 1)

    def test_removing_server_removes_its_virtual_nodes(self):
        for server in ("cache-a", "cache-b", "cache-c"):
            self.ring.add_server(server)
        self.ring.remove_server("cache-b")
        self.assertNotIn("cache-b", self.ring.servers)
        self.assertEqual(self.ring.ring_size, 100)

    def test_removing_unknown_server_does_not_change_ring(self):
        self.ring.add_server("cache-a")
        try:
            self.ring.remove_server("does-not-exist")
        except (KeyError, ValueError):
            pass
        self.assertEqual(self.ring.servers, ["cache-a"])
        self.assertEqual(self.ring.ring_size, 50)

    def test_remaining_server_handles_lookup_after_removal(self):
        self.ring.add_server("cache-a")
        self.ring.add_server("cache-b")
        self.ring.remove_server("cache-b")
        self.assertEqual(self.ring.get_server("important-key"), "cache-a")

    def test_removing_all_servers_returns_ring_to_empty(self):
        self.ring.add_server("cache-a")
        self.ring.remove_server("cache-a")
        self.assertEqual(self.ring.servers, [])
        self.assertEqual(self.ring.ring_size, 0)
        with self.assertRaises((ValueError, RuntimeError)):
            self.ring.get_server("some-key")

    def test_invalid_virtual_node_count_is_rejected(self):
        with self.assertRaises((ValueError, TypeError)):
            ConsistentHashRing(virtual_nodes=0)
        with self.assertRaises((ValueError, TypeError)):
            ConsistentHashRing(virtual_nodes=-1)

    def test_key_distribution_uses_registered_servers_only(self):
        for server in ("cache-a", "cache-b", "cache-c"):
            self.ring.add_server(server)
        counts = Counter(self.ring.get_server(f"customer-{i}") for i in range(2_000))
        self.assertTrue(counts)
        self.assertLessEqual(set(counts), {"cache-a", "cache-b", "cache-c"})

    def test_adding_server_moves_some_but_not_all_keys(self):
        for server in ("cache-a", "cache-b", "cache-c", "cache-d"):
            self.ring.add_server(server)
        keys = [f"customer-{i}" for i in range(5_000)]
        before = {key: self.ring.get_server(key) for key in keys}
        self.ring.add_server("cache-e")
        moved = sum(before[key] != self.ring.get_server(key) for key in keys)
        self.assertGreater(moved, 0)
        self.assertLess(moved, len(keys))

    def test_removed_server_never_owns_keys_after_removal(self):
        for server in ("cache-a", "cache-b", "cache-c"):
            self.ring.add_server(server)
        keys = [f"customer-{i}" for i in range(1_000)]
        self.ring.remove_server("cache-b")
        for key in keys:
            self.assertNotEqual(self.ring.get_server(key), "cache-b")

    def test_ring_size_tracks_server_changes(self):
        for server in ("node-1", "node-2", "node-3"):
            self.ring.add_server(server)
        self.assertEqual(self.ring.ring_size, 150)
        self.ring.remove_server("node-2")
        self.assertEqual(self.ring.ring_size, 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
