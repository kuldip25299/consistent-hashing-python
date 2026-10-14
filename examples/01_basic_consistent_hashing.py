"""
Basic consistent hashing implementation.

This example introduces the core idea:
1. Hash each server onto a circular hash space.
2. Hash each key into the same space.
3. Walk clockwise to find the first server position at or after the key.
4. When a server is added or removed, only a subset of keys should move.

This is an educational implementation. It intentionally uses one ring position
per server; virtual nodes are introduced in a later example.

Run from the repository root:

    python examples/01_basic_consistent_hashing.py
"""

from __future__ import annotations

import hashlib
from bisect import bisect_left
from typing import Dict, List


def stable_hash(value: str) -> int:
    """Return a deterministic, non-negative hash for a string."""
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


class ConsistentHashRing:
    """A minimal consistent hash ring with one position per server."""

    def __init__(self) -> None:
        self._ring: Dict[int, str] = {}
        self._sorted_positions: List[int] = []
        self._servers: set[str] = set()

    @property
    def servers(self) -> List[str]:
        """Return registered server names in sorted order."""
        return sorted(self._servers)

    @property
    def ring_size(self) -> int:
        """Return the number of positions on the ring."""
        return len(self._sorted_positions)

    def add_server(self, server: str) -> None:
        """Add a server to the ring. Adding the same server twice is a no-op."""
        self._validate_name(server)
        if server in self._servers:
            return

        position = stable_hash(f"server:{server}")
        suffix = 0
        while position in self._ring:
            suffix += 1
            position = stable_hash(f"server:{server}#collision-{suffix}")

        self._ring[position] = server
        self._sorted_positions.append(position)
        self._sorted_positions.sort()
        self._servers.add(server)

    def remove_server(self, server: str) -> None:
        """Remove a server. Raises KeyError if it is not registered."""
        if server not in self._servers:
            raise KeyError(f"Server is not registered: {server}")

        position = stable_hash(f"server:{server}")
        if self._ring.get(position) != server:
            suffix = 0
            while self._ring.get(position) != server:
                suffix += 1
                position = stable_hash(f"server:{server}#collision-{suffix}")

        del self._ring[position]
        self._sorted_positions.remove(position)
        self._servers.remove(server)

    def get_server(self, key: str) -> str:
        """Return the server responsible for a key; raise if the ring is empty."""
        if not self._sorted_positions:
            raise ValueError("Cannot route a key: the hash ring has no servers.")

        key_position = stable_hash(f"key:{key}")
        index = bisect_left(self._sorted_positions, key_position)
        if index == len(self._sorted_positions):
            index = 0  # Wrap around to the first ring position.
        return self._ring[self._sorted_positions[index]]

    def describe(self) -> None:
        """Print ring positions for learning and debugging."""
        print("Hash ring positions:")
        for position in self._sorted_positions:
            print(f"  {position:20d} -> {self._ring[position]}")

    @staticmethod
    def _validate_name(server: str) -> None:
        if not isinstance(server, str) or not server.strip():
            raise ValueError("Server name must be a non-empty string.")


def main() -> None:
    ring = ConsistentHashRing()
    for server in ("cache-a", "cache-b", "cache-c"):
        ring.add_server(server)

    keys = [
        "user:1001",
        "user:1002",
        "user:1003",
        "session:abc",
        "product:5001",
        "cart:9001",
    ]

    print("=== Basic Consistent Hashing ===")
    print(f"Servers: {ring.servers}")
    print(f"Ring positions: {ring.ring_size}")
    ring.describe()

    print("\n=== Initial key routing ===")
    before = {}
    for key in keys:
        before[key] = ring.get_server(key)
        print(f"{key:16s} -> {before[key]}")

    print("\n=== Add cache-d ===")
    ring.add_server("cache-d")
    moved_after_add = 0
    for key in keys:
        after = ring.get_server(key)
        moved = before[key] != after
        moved_after_add += moved
        print(f"{key:16s} -> {after}{' (moved)' if moved else ''}")
    print(f"Keys moved after adding a server: {moved_after_add}/{len(keys)}")

    print("\n=== Remove cache-b ===")
    before_remove = {key: ring.get_server(key) for key in keys}
    ring.remove_server("cache-b")
    moved_after_remove = sum(
        before_remove[key] != ring.get_server(key) for key in keys
    )
    for key in keys:
        print(f"{key:16s} -> {ring.get_server(key)}")
    print(f"Keys moved after removing cache-b: {moved_after_remove}/{len(keys)}")

    print("\nThis basic version has one position per server.")
    print("The virtual-node example improves distribution across servers.")


if __name__ == "__main__":
    main()

