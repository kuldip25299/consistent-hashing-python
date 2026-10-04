# Virtual Nodes in Consistent Hashing

## 1. The Problem with One Position per Server

In the previous implementation, each physical server was assigned one position on the hash ring. This demonstrates the core algorithm, but one position per server can produce uneven key distribution: some servers may own large ring segments while others own small ones.

## 2. What Is a Virtual Node?

A **virtual node** (often called a *vnode* or *replica*) is an additional position on the hash ring that represents the same physical server.

For example, with three virtual nodes per server:

```text
Physical server A -> A#0, A#1, A#2
Physical server B -> B#0, B#1, B#2
Physical server C -> C#0, C#1, C#2
```

Each virtual node has a distinct hash position. When a key is hashed, the algorithm finds the first virtual node clockwise from the key's position, then routes the key to the physical server represented by that virtual node.

The routing rule stays the same. The ring simply has more positions.

## 3. Why Virtual Nodes Help

More independently hashed positions divide the ring into more segments. A physical server owns several smaller segments distributed around the ring instead of one potentially large segment. This generally improves expected distribution across servers.

It is a statistical improvement, not a guarantee of perfect equality. Actual results depend on the hash function, number of keys, server count, and virtual-node count.

## 4. Complete Implementation

Create this file:

`examples/04_virtual_nodes.py`

```python
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

            # Resolve an extremely unlikely hash-position collision.
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

        # Wrap around to the first position if the key is past the last node.
        if index == len(self._sorted_positions):
            index = 0

        return self._ring[self._sorted_positions[index]]

    @property
    def servers(self) -> list[str]:
        """Return physical server names in sorted order."""
        return sorted(self._servers)


def measure_distribution(
    ring: ConsistentHashRing,
    keys: list[str],
) -> dict[str, int]:
    """Count how many keys are assigned to each physical server."""
    counts = Counter(ring.get_server(key) for key in keys)
    return {server: counts.get(server, 0) for server in ring.servers}


def print_distribution(
    title: str,
    ring: ConsistentHashRing,
    keys: list[str],
) -> None:
    """Print key counts and percentages per physical server."""
    counts = measure_distribution(ring, keys)
    total = len(keys)

    print(f"\\n{title}")
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

    # Baseline: one ring position per physical server.
    basic_ring = ConsistentHashRing(virtual_nodes=1)
    for server in server_names:
        basic_ring.add_server(server)

    # Compare against 100 positions per physical server.
    virtual_ring = ConsistentHashRing(virtual_nodes=100)
    for server in server_names:
        virtual_ring.add_server(server)

    print_distribution("Baseline: one position per server", basic_ring, keys)
    print_distribution("Virtual nodes: 100 positions per server", virtual_ring, keys)


if __name__ == "__main__":
    main()
```

## 5. Run It

From the repository root:

```bash
python examples/04_virtual_nodes.py
```

The example uses only the Python standard library. No Redis, database, or third-party package is required.

## 6. Understand the Output

The script prints the number and percentage of keys assigned to each physical server for both configurations.

With four servers and 100,000 keys, a perfectly even distribution would be approximately 25,000 keys per server (25%). The actual result will not be perfectly even.

Compare the two sections:

- **One position per server:** ownership may be uneven because each server owns a single ring segment.
- **100 virtual nodes per server:** ownership is spread across more segments, which will often improve balance.

Do not assume virtual nodes must improve every small sample. Distribution is statistical; measure it using a representative workload.

## 7. Choosing a Virtual-Node Count

There is no universal best value. Start with a reasonable count, measure distribution using representative keys and server counts, then adjust based on the result and operational costs.

| Virtual nodes per server | General trade-off |
|---:|---|
| 1 | Small ring, but distribution may be uneven |
| 10 | More positions with modest metadata |
| 100 | Useful value for experiments and comparisons |
| 500+ | More positions and update work; benchmark the benefit |

These are illustrative comparison points, not universal production defaults.

Increasing the virtual-node count means:

- More ring positions must be stored.
- Adding or removing a server creates or removes more positions.
- Ring updates and sorting require more work in this simple implementation.
- Better key-count balance still does not guarantee balanced CPU, memory, or request latency.

## 8. Complexity

Let \(S\) be the number of physical servers, \(V\) the virtual nodes per server, and \(R = S \times V\) the total number of ring positions.

| Operation | This implementation |
|---|---|
| Add a server | Adds \(V\) positions and sorts the resulting ring; up to \(O(R \log R)\) sorting work |
| Remove a server | Scans ring positions and rebuilds the sorted-position list |
| Route a key | \(O(\log R)\) using binary search |
| Ring metadata | \(O(R)\) positions |

The add/remove paths prioritize readability. A production implementation may use different data structures or incremental update strategies.

## 9. What Virtual Nodes Do Not Solve

Virtual nodes improve the expected distribution of key ownership. They do not automatically solve:

- **Hot keys:** a few keys may receive much more traffic than others.
- **Unequal server capacity:** identical vnode counts assume servers should own roughly similar shares. Different-capacity servers may need weighted virtual-node counts.
- **Uneven request cost:** equal key counts do not guarantee equal CPU usage, memory use, or latency.
- **All data movement:** adding or removing a server still changes ownership for some keys.

Measure actual workload as well as key distribution.

## 10. Key Takeaways

- A physical server can be represented by many virtual nodes on the ring.
- Each virtual node has its own position but maps to the same physical server.
- More virtual nodes generally improve expected distribution by dividing the ring into more segments.
- The result is statistical, not a guarantee of equal load.
- More virtual nodes increase metadata and ring-update work.
- Choose the count through measurement rather than assuming more is always better.

## Next Step

Next, measure key redistribution when servers are added or removed, and compare consistent hashing with naive modulo hashing.
