# Measuring Key Redistribution

## 1. Why Measure Key Redistribution?

Consistent hashing is useful because adding or removing a server should move only a relatively small portion of keys.

This matters in distributed caches, application routing, sharded storage, distributed databases, and partitioned message systems.

The important question is:

> When the number of servers changes, how many existing keys are forced to move?

This document turns that question into a measurable experiment.

We compare:

1. Naive modulo hashing
2. Consistent hashing with one position per server
3. Consistent hashing with virtual nodes

The goal is to understand the trade-off through measurement rather than assumptions.

## 2. The Experiment

Start with four servers:

```text
cache-01
cache-02
cache-03
cache-04
```

Then add:

```text
cache-05
```

Use the same fixed set of 100,000 keys before and after the topology change.

For every algorithm:

1. Map all keys to the original cluster.
2. Add `cache-05`.
3. Map the same keys again.
4. Compare old and new assignments.
5. Count moved keys.
6. Calculate the movement percentage.

The input keys remain identical. We are measuring the effect of changing the server topology.

## 3. What Is a Moved Key?

A key moved when its assigned server changes.

```text
Before:

user-100 -> cache-02
user-101 -> cache-03
user-102 -> cache-01
```

After:

```text
user-100 -> cache-02
user-101 -> cache-05   <- moved
user-102 -> cache-01
```

The calculation is:

```text
moved_keys = number of keys where old_server != new_server

movement_percentage =
    moved_keys / total_keys * 100
```

## 4. Expected Behavior of Modulo Hashing

A common strategy is:

```python
server_index = hash(key) % number_of_servers
```

With four servers:

```text
hash(key) % 4
```

With five:

```text
hash(key) % 5
```

Changing the divisor changes the mapping for many keys. This is the redistribution problem that consistent hashing is designed to reduce.

## 5. Expected Behavior of Consistent Hashing

With consistent hashing, servers occupy positions on a hash ring.

A key is assigned to the first server position clockwise from its hash position.

When a new server is added, it captures only specific portions of the ring.

Therefore, most keys can keep their existing owner.

## 6. Why Virtual Nodes Matter

A physical server can be represented by multiple virtual nodes.

```text
cache-01 -> 100 virtual nodes
cache-02 -> 100 virtual nodes
cache-03 -> 100 virtual nodes
cache-04 -> 100 virtual nodes
```

This usually improves distribution because each physical server owns multiple smaller ring segments.

Virtual nodes do not mean zero redistribution. When `cache-05` is added, its virtual nodes still capture portions of the existing ring.

## 7. Complete Experiment

Create:

```text
examples/05_measuring_key_movement.py
```

Copy the complete implementation below into that file.

```python
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

            # Extremely unlikely collision handling.
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


def build_modulo_mapping(
    keys: list[str],
    servers: list[str],
) -> dict[str, str]:
    """Build key-to-server mapping using modulo hashing."""
    return {key: modulo_server(key, servers) for key in keys}


def build_ring_mapping(
    keys: list[str],
    ring: ConsistentHashRing,
) -> dict[str, str]:
    """Build key-to-server mapping using consistent hashing."""
    return {key: ring.get_server(key) for key in keys}


def count_moved_keys(
    before: dict[str, str],
    after: dict[str, str],
) -> int:
    """Count keys whose assigned server changed."""
    if before.keys() != after.keys():
        raise ValueError("Before and after mappings must contain the same keys")

    return sum(1 for key in before if before[key] != after[key])


def movement_percentage(moved_keys: int, total_keys: int) -> float:
    """Calculate the percentage of keys that moved."""
    if total_keys == 0:
        return 0.0
    return moved_keys / total_keys * 100


def print_result(
    algorithm: str,
    moved_keys: int,
    total_keys: int,
) -> None:
    """Print one experiment result."""
    percentage = movement_percentage(moved_keys, total_keys)

    print(algorithm)
    print("-" * len(algorithm))
    print(f"Moved keys:       {moved_keys:,}")
    print(f"Total keys:       {total_keys:,}")
    print(f"Movement:         {percentage:.2f}%")
    print()


def run_experiment(
    keys: list[str],
    initial_servers: list[str],
    new_server: str,
) -> None:
    """Run the same add-server experiment for all strategies."""

    updated_servers = [*initial_servers, new_server]

    # 1. Naive modulo hashing.
    modulo_before = build_modulo_mapping(keys, initial_servers)
    modulo_after = build_modulo_mapping(keys, updated_servers)
    modulo_moved = count_moved_keys(modulo_before, modulo_after)

    # 2. Consistent hashing with one position per server.
    basic_before_ring = ConsistentHashRing(virtual_nodes=1)
    for server in initial_servers:
        basic_before_ring.add_server(server)

    basic_after_ring = ConsistentHashRing(virtual_nodes=1)
    for server in updated_servers:
        basic_after_ring.add_server(server)

    basic_before = build_ring_mapping(keys, basic_before_ring)
    basic_after = build_ring_mapping(keys, basic_after_ring)
    basic_moved = count_moved_keys(basic_before, basic_after)

    # 3. Consistent hashing with 100 virtual nodes per server.
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
    print_result(
        "2. Consistent hashing - 1 position/server",
        basic_moved,
        len(keys),
    )
    print_result(
        "3. Consistent hashing - 100 virtual nodes/server",
        vnode_moved,
        len(keys),
    )


def main() -> None:
    """Generate a deterministic workload and run the experiment."""
    keys = [f"user-{number}" for number in range(100_000)]

    initial_servers = [
        "cache-01",
        "cache-02",
        "cache-03",
        "cache-04",
    ]

    run_experiment(
        keys=keys,
        initial_servers=initial_servers,
        new_server="cache-05",
    )


if __name__ == "__main__":
    main()
```

## 8. Run the Experiment

From the repository root:

```bash
python examples/05_measuring_key_movement.py
```

No third-party dependency is required.

The experiment uses:

```text
100,000 keys
4 initial servers
1 newly added server
```

You should see three result sections:

```text
============================================================
KEY REDISTRIBUTION EXPERIMENT
============================================================

Initial servers: cache-01, cache-02, cache-03, cache-04
Added server:    cache-05
Total keys:      100,000

1. Naive modulo hashing
-----------------------
Moved keys:       ...
Total keys:       100,000
Movement:         ...%

2. Consistent hashing - 1 position/server
------------------------------------------
Moved keys:       ...
Total keys:       100,000
Movement:         ...%

3. Consistent hashing - 100 virtual nodes/server
------------------------------------------------
Moved keys:       ...
Total keys:       100,000
Movement:         ...%
```

The exact percentages depend on the deterministic hash positions used by this implementation.

## 9. What We Should Expect

The important comparison is the pattern, not the exact number from one run.

### Modulo hashing

```text
Server count changes
        ↓
Hash divisor changes
        ↓
Many keys can change owner
```

### Consistent hashing

```text
Server added to ring
        ↓
New server captures portions of ring
        ↓
Keys in those portions move
        ↓
Other keys keep their owner
```

This is the core scalability advantage of consistent hashing.

## 10. Why Modulo Hashing Moves So Many Keys

Suppose there are four servers:

```text
hash(key) % 4
```

After adding another server:

```text
hash(key) % 5
```

A key that previously produced:

```text
hash(key) % 4 == 2
```

may produce:

```text
hash(key) % 5 == 4
```

The key therefore moves from one server to another.

This happens independently for a large number of keys.

The problem is not that modulo hashing is incorrect. The problem is that its mapping is highly sensitive to the number of partitions.

## 11. Why Consistent Hashing Moves Fewer Keys

Consistent hashing places both keys and servers into the same hash space.

For example:

```text
0 ------------------------------------------ MAX
        A          B          C          D
```

A key searches clockwise for its owner.

After adding E:

```text
0 ------------------------------------------ MAX
        A       E  B          C          D
```

Only the ring segment captured by `E` changes ownership. Other segments keep their previous owner.

That is the central idea.

## 12. Redistribution vs Load Balance

These are different properties.

### Redistribution

How many existing keys change owners when topology changes?

```text
Server added
    ↓
How many keys move?
```

Consistent hashing is designed to minimize unnecessary movement.

### Distribution

How evenly are keys spread across servers?

```text
Server A -> 28%
Server B -> 24%
Server C -> 23%
Server D -> 25%
```

Virtual nodes help improve this property.

A system can have low redistribution but poor balance, good balance but high redistribution, or both.

## 13. Virtual Nodes Create a Trade-off

If:

```text
servers = 100
virtual_nodes = 100
```

then:

```text
total ring positions = 10,000
```

If:

```text
servers = 1,000
virtual_nodes = 500
```

then:

```text
total ring positions = 500,000
```

More virtual nodes can improve statistical balance, but they also increase metadata and ring-update work.

Therefore:

> More virtual nodes is not automatically better.

Select the value using measurements and workload requirements.

## 14. A Better Production Experiment

The example changes topology once:

```text
4 -> 5
```

A stronger benchmark tests multiple changes:

```text
2 -> 3
3 -> 4
4 -> 5
5 -> 6
...
10 -> 11
```

For every change, record:

```text
server_count
virtual_nodes
total_keys
moved_keys
movement_percentage
```

Then compare modulo hashing, consistent hashing, and consistent hashing with virtual nodes under the same workload.

## 15. What This Experiment Does Not Measure

This experiment measures **key ownership changes**.

It does not measure:

- Network traffic
- Cache warm-up time
- Database migration time
- Request latency
- CPU usage
- Memory usage
- Hot-key behavior
- Replication
- Failover time

Moving 10% of keys does not necessarily mean 10% of application traffic moves. One hot key can receive more traffic than thousands of normal keys.

Key movement is important, but it is not the complete system-performance picture.

## 16. Production Interpretation

Suppose a cache cluster contains:

```text
100 million keys
```

and adding one server causes:

```text
70 million keys
```

to change ownership.

The application may need to repopulate a huge portion of the cache.

That can create:

```text
Cache misses
    ↓
More database requests
    ↓
Higher database load
    ↓
Higher latency
    ↓
Potential cascading failures
```

With consistent hashing, the objective is to keep unnecessary ownership changes much smaller.

This is why the algorithm is useful beyond a theoretical data-structure exercise.

## 17. Key Takeaways

1. Server topology changes are normal in distributed systems.
2. Naive modulo hashing is highly sensitive to the number of servers.
3. Changing the modulo divisor can move a large portion of existing keys.
4. Consistent hashing limits ownership changes to affected ring segments.
5. Virtual nodes improve ownership distribution across physical servers.
6. Virtual nodes do not eliminate redistribution.
7. Key redistribution and load distribution are different metrics.
8. The correct design should be measured using realistic workloads.
9. More virtual nodes increase metadata and update costs.
10. Consistent hashing provides a useful trade-off between scalability and data movement.

## Next Step

The next document will focus on production concerns of a consistent-hashing implementation: server failure, server removal, ring updates, deterministic hashing, collision handling, and the practical trade-offs between a simple implementation and a production-grade implementation.
