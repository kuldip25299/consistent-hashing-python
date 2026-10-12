from __future__ import annotations

import hashlib
from bisect import bisect_left
from collections import Counter
from dataclasses import dataclass, field


def stable_hash(value: str) -> int:
    """Return a deterministic 64-bit hash for a string."""
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


@dataclass
class ConsistentHashRing:
    """Consistent hash ring with configurable virtual nodes per server."""

    virtual_nodes: int = 1
    _ring: dict[int, str] = field(default_factory=dict, init=False)
    _sorted_positions: list[int] = field(default_factory=list, init=False)
    _servers: set[str] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        if self.virtual_nodes < 1:
            raise ValueError("virtual_nodes must be at least 1")

    def add_server(self, server: str) -> None:
        """Add a physical server and all of its virtual nodes."""
        if not server:
            raise ValueError("server name must not be empty")
        if server in self._servers:
            return

        self._servers.add(server)

        for replica in range(self.virtual_nodes):
            node_id = f"server:{server}#replica-{replica}"
            position = stable_hash(node_id)
            while position in self._ring:
                node_id += "#collision"
                position = stable_hash(node_id)

            self._ring[position] = server
            self._sorted_positions.append(position)

        self._sorted_positions.sort()

    def remove_server(self, server: str) -> None:
        """Remove a physical server and all of its virtual nodes."""
        if server not in self._servers:
            return

        self._servers.remove(server)
        positions = [
            position
            for position, physical_server in self._ring.items()
            if physical_server == server
        ]

        for position in positions:
            del self._ring[position]

        if positions:
            removed = set(positions)
            self._sorted_positions = [
                position
                for position in self._sorted_positions
                if position not in removed
            ]

    def get_server(self, key: str) -> str:
        """Return the physical server responsible for a key."""
        if not self._sorted_positions:
            raise RuntimeError("Cannot route keys: no servers are available")

        key_position = stable_hash(f"key:{key}")
        index = bisect_left(self._sorted_positions, key_position)
        if index == len(self._sorted_positions):
            index = 0

        return self._ring[self._sorted_positions[index]]

    @property
    def servers(self) -> list[str]:
        return sorted(self._servers)


def measure_distribution(
    ring: ConsistentHashRing,
    keys: list[str],
) -> dict[str, int]:
    counts = Counter(ring.get_server(key) for key in keys)
    return {server: counts.get(server, 0) for server in ring.servers}


def print_distribution(
    title: str,
    ring: ConsistentHashRing,
    keys: list[str],
) -> None:
    counts = measure_distribution(ring, keys)
    total = len(keys)

    print(f"\n{title}")
    print("-" * len(title))
    print(f"Physical servers: {len(ring.servers)}")
    print(f"Virtual nodes per server: {ring.virtual_nodes}")
    print(f"Total keys: {total:,}")

    for server, count in counts.items():
        percentage = (count / total * 100) if total else 0.0
        print(f"{server:12} {count:8,} keys  ({percentage:6.2f}%)")


def main() -> None:
    server_names = ["cache-01", "cache-02", "cache-03", "cache-04"]
    keys = [f"user-{number}" for number in range(100_000)]

    basic_ring = ConsistentHashRing(virtual_nodes=1)
    for server in server_names:
        basic_ring.add_server(server)

    virtual_ring = ConsistentHashRing(virtual_nodes=100)
    for server in server_names:
        virtual_ring.add_server(server)

    print_distribution("Baseline: one position per server", basic_ring, keys)
    print_distribution("Virtual nodes: 100 positions per server", virtual_ring, keys)


if __name__ == "__main__":
    main()
