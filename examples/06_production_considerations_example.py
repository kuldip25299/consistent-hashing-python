from __future__ import annotations

import hashlib
from bisect import bisect_left
from dataclasses import dataclass, field


def stable_hash(value: str) -> int:
    """Return a deterministic 64-bit integer hash."""
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


@dataclass
class ConsistentHashRing:
    """Simple production-oriented learning implementation."""

    virtual_nodes: int = 100
    _ring: dict[int, str] = field(default_factory=dict, init=False)
    _sorted_positions: list[int] = field(default_factory=list, init=False)
    _servers: set[str] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        if self.virtual_nodes < 1:
            raise ValueError("virtual_nodes must be at least 1")

    def add_server(self, server: str) -> None:
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
        if server not in self._servers:
            return

        self._servers.remove(server)
        positions = [
            position
            for position, owner in self._ring.items()
            if owner == server
        ]

        for position in positions:
            del self._ring[position]

        removed = set(positions)
        self._sorted_positions = [
            position
            for position in self._sorted_positions
            if position not in removed
        ]

    def get_server(self, key: str) -> str:
        if not self._sorted_positions:
            raise RuntimeError("Cannot route key: no servers are available")

        position = stable_hash(f"key:{key}")
        index = bisect_left(self._sorted_positions, position)

        if index == len(self._sorted_positions):
            index = 0

        return self._ring[self._sorted_positions[index]]

    @property
    def servers(self) -> list[str]:
        return sorted(self._servers)

    @property
    def ring_size(self) -> int:
        return len(self._sorted_positions)


def main() -> None:
    ring = ConsistentHashRing(virtual_nodes=100)

    for server in ["cache-01", "cache-02", "cache-03", "cache-04"]:
        ring.add_server(server)

    print("Servers:", ring.servers)
    print("Ring positions:", ring.ring_size)
    print()

    keys = [
        "user-100",
        "user-101",
        "user-102",
        "user-103",
        "user-104",
    ]

    print("Initial routing:")
    for key in keys:
        print(f"{key} -> {ring.get_server(key)}")

    ring.add_server("cache-05")

    print("\nAfter adding cache-05:")
    for key in keys:
        print(f"{key} -> {ring.get_server(key)}")

    ring.remove_server("cache-03")

    print("\nAfter removing cache-03:")
    for key in keys:
        print(f"{key} -> {ring.get_server(key)}")


if __name__ == "__main__":
    main()
