"""Production-ready-ish consistent hashing example.

This example is intentionally dependency-free and educational. It demonstrates:
- deterministic hashing
- virtual nodes
- add/remove server
- O(log R) lookup
- collision handling
- optional server weights
- ring inspection
- key distribution measurement
- key movement measurement

It does NOT implement service discovery, health checks, replication, or data
migration. Those concerns belong outside the routing structure.
"""

from __future__ import annotations

import bisect
import hashlib
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple



def stable_hash(value: str) -> int:
    """Return a deterministic 64-bit hash for a string."""
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


@dataclass
class ConsistentHashRing:
    """Consistent hash ring with virtual nodes.

    ``virtual_nodes`` is the base number of virtual nodes assigned to a server.
    A server with weight=2 receives roughly twice as many virtual nodes.
    """

    virtual_nodes: int = 100
    _ring: Dict[int, str] = field(default_factory=dict, init=False)
    _sorted_positions: List[int] = field(default_factory=list, init=False)
    _server_weights: Dict[str, float] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        if self.virtual_nodes <= 0:
            raise ValueError("virtual_nodes must be greater than zero")

    @property
    def servers(self) -> Tuple[str, ...]:
        """Return servers currently registered with the ring."""
        return tuple(sorted(self._server_weights))

    @property
    def ring_size(self) -> int:
        """Return the number of virtual-node positions on the ring."""
        return len(self._sorted_positions)

    def add_server(self, server: str, weight: float = 1.0) -> None:
        """Add a server to the ring.

        ``weight`` controls relative ownership. For example, weight=2 gives a
        server approximately twice the virtual nodes of a weight=1 server.
        """
        if not server:
            raise ValueError("server must not be empty")
        if weight <= 0:
            raise ValueError("weight must be greater than zero")
        if server in self._server_weights:
            raise ValueError(f"server already exists: {server}")

        replicas = max(1, round(self.virtual_nodes * weight))
        self._server_weights[server] = weight

        for replica in range(replicas):
            position = self._find_free_position(f"server:{server}#replica-{replica}")
            self._ring[position] = server
            self._sorted_positions.append(position)

        self._sorted_positions.sort()

    def remove_server(self, server: str) -> None:
        """Remove a server and all of its virtual nodes."""
        if server not in self._server_weights:
            raise KeyError(f"server does not exist: {server}")

        positions = [
            position
            for position, owner in self._ring.items()
            if owner == server
        ]

        for position in positions:
            del self._ring[position]

        self._sorted_positions = [
            position
            for position in self._sorted_positions
            if position not in set(positions)
        ]
        del self._server_weights[server]

    def get_server(self, key: str) -> Optional[str]:
        """Return the server responsible for a key.

        Lookup moves clockwise from the key's hash position. If the key falls
        beyond the last ring position, lookup wraps to the first position.
        """
        if not self._sorted_positions:
            return None

        key_position = stable_hash(f"key:{key}")
        index = bisect.bisect_left(self._sorted_positions, key_position)

        if index == len(self._sorted_positions):
            index = 0

        return self._ring[self._sorted_positions[index]]

    def distribution(self, keys: Iterable[str]) -> Dict[str, int]:
        """Count how many keys are routed to each server."""
        result = {server: 0 for server in self.servers}
        for key in keys:
            server = self.get_server(key)
            if server is not None:
                result[server] += 1
        return result

    def ring_entries(self) -> List[Tuple[int, str]]:
        """Return ring positions and owners in clockwise order."""
        return [
            (position, self._ring[position])
            for position in self._sorted_positions
        ]

    def _find_free_position(self, virtual_node_name: str) -> int:
        """Find a deterministic unused position for a virtual node.

        Hash collisions are extremely unlikely with 64-bit positions, but a
        production implementation should still handle them explicitly.
        """
        candidate = stable_hash(virtual_node_name)
        collision = 0

        while candidate in self._ring:
            collision += 1
            candidate = stable_hash(f"{virtual_node_name}#collision-{collision}")

        return candidate


def measure_movement(
    before: ConsistentHashRing,
    after: ConsistentHashRing,
    keys: Sequence[str],
) -> Tuple[int, float]:
    """Return moved-key count and movement percentage."""
    if not keys:
        return 0, 0.0

    moved = sum(
        before.get_server(key) != after.get_server(key)
        for key in keys
    )
    percentage = moved / len(keys) * 100
    return moved, percentage


def build_ring(servers: Mapping[str, float], virtual_nodes: int = 100) -> ConsistentHashRing:
    """Build a ring from ``server -> weight`` definitions."""
    ring = ConsistentHashRing(virtual_nodes=virtual_nodes)
    for server, weight in servers.items():
        ring.add_server(server, weight=weight)
    return ring


def print_distribution(title: str, distribution: Mapping[str, int]) -> None:
    print(f"\n{title}")
    total = sum(distribution.values())
    for server, count in sorted(distribution.items()):
        percentage = (count / total * 100) if total else 0.0
        print(f"  {server:12} {count:6} keys ({percentage:6.2f}%)")


def main() -> None:
    keys = [f"user-{number}" for number in range(100_000)]

    ring = ConsistentHashRing(virtual_nodes=100)
    for server in ("cache-01", "cache-02", "cache-03", "cache-04"):
        ring.add_server(server)

    print("=== Initial Ring ===")
    print(f"Servers: {ring.servers}")
    print(f"Virtual-node positions: {ring.ring_size}")

    print("\n=== Key Routing ===")
    for key in ("user-100", "user-200", "user-300", "user-400", "user-500"):
        print(f"  {key:12} -> {ring.get_server(key)}")

    distribution_before = ring.distribution(keys)
    print_distribution("=== Initial Distribution ===", distribution_before)

    expanded_ring = build_ring(
        {
            "cache-01": 1.0,
            "cache-02": 1.0,
            "cache-03": 1.0,
            "cache-04": 1.0,
            "cache-05": 1.0,
        },
        virtual_nodes=100,
    )

    moved, percentage = measure_movement(ring, expanded_ring, keys)
    print("\n=== Adding cache-05 ===")
    print(f"Moved keys: {moved:,} / {len(keys):,}")
    print(f"Movement:   {percentage:.2f}%")

    distribution_after = expanded_ring.distribution(keys)
    print_distribution("=== Distribution After Adding Server ===", distribution_after)

    weighted_ring = build_ring(
        {
            "cache-small": 1.0,
            "cache-large": 2.0,
        },
        virtual_nodes=100,
    )

    weighted_distribution = weighted_ring.distribution(keys)
    print_distribution("=== Weighted Distribution Example ===", weighted_distribution)

    print("\n=== Removing cache-03 ===")
    removal_ring = build_ring(
        {
            "cache-01": 1.0,
            "cache-02": 1.0,
            "cache-03": 1.0,
            "cache-04": 1.0,
        },
        virtual_nodes=100,
    )
    removal_ring.remove_server("cache-03")
    print(f"Servers after removal: {removal_ring.servers}")
    print(f"cache-03 lookup: {removal_ring.get_server('user-100')}")


if __name__ == "__main__":
    main()
