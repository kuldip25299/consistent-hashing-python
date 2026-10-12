from __future__ import annotations

import hashlib
from bisect import bisect_left
from dataclasses import dataclass, field


def stable_hash(value: str) -> int:
    """Return a deterministic 64-bit integer hash."""
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def modulo_server(key: str, servers: list[str]) -> str:
    """Assign a key using naive modulo hashing."""
    if not servers:
        raise RuntimeError("Cannot route key: no servers are available")
    key_hash = stable_hash(f"key:{key}")
    return servers[key_hash % len(servers)]


@dataclass
class ConsistentHashRing:
    """Simple consistent hash ring with configurable virtual nodes."""

    virtual_nodes: int = 1
    _ring: dict[int, str] = field(default_factory=dict, init=False)
    _sorted_positions: list[int] = field(default_factory=list, init=False)
    _servers: set[str] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        if self.virtual_nodes < 1:
            raise ValueError("virtual_nodes must be at least 1")

    def add_server(self, server: str) -> None:
        """Add a physical server and its virtual nodes."""
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
        positions_to_remove = [
            position
            for position, physical_server in self._ring.items()
            if physical_server == server
        ]
        for position in positions_to_remove:
            del self._ring[position]

        if positions_to_remove:
            removed = set(positions_to_remove)
            self._sorted_positions = [
                position
                for position in self._sorted_positions
                if position not in removed
            ]

    def get_server(self, key: str) -> str:
        """Return the physical server responsible for a key."""
        if not self._sorted_positions:
            raise RuntimeError("Cannot route key: no servers are available")

        key_position = stable_hash(f"key:{key}")
        index = bisect_left(self._sorted_positions, key_position)
        if index == len(self._sorted_positions):
            index = 0
        return self._ring[self._sorted_positions[index]]

    @property
    def servers(self) -> list[str]:
        """Return physical servers in deterministic order."""
        return sorted(self._servers)


def build_modulo_mapping(keys: list[str], servers: list[str]) -> dict[str, str]:
    """Build key-to-server mapping using modulo hashing."""
    return {key: modulo_server(key, servers) for key in keys}


def build_ring_mapping(keys: list[str], ring: ConsistentHashRing) -> dict[str, str]:
    """Build key-to-server mapping using consistent hashing."""
    return {key: ring.get_server(key) for key in keys}


def count_moved_keys(before: dict[str, str], after: dict[str, str]) -> int:
    """Count keys whose assigned server changed."""
    if before.keys() != after.keys():
        raise ValueError("Before and after mappings must contain the same keys")
    return sum(1 for key in before if before[key] != after[key])


def movement_percentage(moved_keys: int, total_keys: int) -> float:
    """Calculate the percentage of keys that moved."""
    if total_keys == 0:
        return 0.0
    return moved_keys / total_keys * 100


def print_result(algorithm: str, moved_keys: int, total_keys: int) -> None:
    """Print one experiment result."""
    percentage = movement_percentage(moved_keys, total_keys)
    print(algorithm)
    print("-" * len(algorithm))
    print(f"Moved keys:       {moved_keys:,}")
    print(f"Total keys:       {total_keys:,}")
    print(f"Movement:         {percentage:.2f}%")
    print()


def run_experiment(keys: list[str], initial_servers: list[str], new_server: str) -> None:
    """Run the same add-server experiment for all strategies."""
    updated_servers = [*initial_servers, new_server]

    modulo_before = build_modulo_mapping(keys, initial_servers)
    modulo_after = build_modulo_mapping(keys, updated_servers)
    modulo_moved = count_moved_keys(modulo_before, modulo_after)

    basic_before_ring = ConsistentHashRing(virtual_nodes=1)
    for server in initial_servers:
        basic_before_ring.add_server(server)
    basic_after_ring = ConsistentHashRing(virtual_nodes=1)
    for server in updated_servers:
        basic_after_ring.add_server(server)
    basic_before = build_ring_mapping(keys, basic_before_ring)
    basic_after = build_ring_mapping(keys, basic_after_ring)
    basic_moved = count_moved_keys(basic_before, basic_after)

    vnode_before_ring = ConsistentHashRing(virtual_nodes=100)
    for server in initial_servers:
        vnode_before_ring.add_server(server)
    vnode_after_ring = ConsistentHashRing(virtual_nodes=100)
    for server in updated_servers:
        vnode_after_ring.add_server(server)
    vnode_before = build_ring_mapping(keys, vnode_before_ring)
    vnode_after = build_ring_mapping(keys, vnode_after_ring)
    vnode_moved = count_moved_keys(vnode_before, vnode_after)

    print()
    print("=" * 60)
    print("KEY REDISTRIBUTION EXPERIMENT")
    print("=" * 60)
    print()
    print(f"Initial servers: {', '.join(initial_servers)}")
    print(f"Added server:    {new_server}")
    print(f"Total keys:      {len(keys):,}")
    print()
    print_result("1. Naive modulo hashing", modulo_moved, len(keys))
    print_result("2. Consistent hashing - 1 position/server", basic_moved, len(keys))
    print_result("3. Consistent hashing - 100 virtual nodes/server", vnode_moved, len(keys))


def main() -> None:
    """Generate a deterministic workload and run the experiment."""
    keys = [f"user-{number}" for number in range(100_000)]
    initial_servers = ["cache-01", "cache-02", "cache-03", "cache-04"]
    run_experiment(keys=keys, initial_servers=initial_servers, new_server="cache-05")


if __name__ == "__main__":
    main()
