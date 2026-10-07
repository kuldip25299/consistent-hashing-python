# Production-Ready Consistent Hashing Implementation

## 1. Where We Are

So far, this repository has built consistent hashing step by step:

1. Business problem
2. Naive modulo hashing
3. Measuring key redistribution
4. How consistent hashing works
5. Basic implementation
6. Virtual nodes
7. Measuring key redistribution with virtual nodes
8. Production considerations

The next step is to combine those ideas into one reusable implementation.

This file focuses on the **routing component itself**.

It is still intentionally small. We are not building a complete distributed cache, database, service-discovery system, or consensus protocol.

The goal is to create a consistent-hashing component that is:

- deterministic
- reusable
- easy to test
- safe to update
- based on virtual nodes
- efficient for lookups
- explicit about its responsibilities

---

## 2. What We Want From the Implementation

A useful consistent-hashing component should support:

```text
Add server
Remove server
Route key
Inspect servers
Inspect ring size
Measure ownership
```

Conceptually:

```text
                    ConsistentHashRing
                           |
             +-------------+-------------+
             |             |             |
          add_server   remove_server   get_server
             |             |             |
             +-------------+-------------+
                           |
                       Hash Ring
                           |
                    Virtual Nodes
```

The routing path should remain simple:

```text
key
 |
 v
stable hash
 |
 v
binary search
 |
 v
next virtual node clockwise
 |
 v
physical server
```

---

## 3. Responsibilities

The class in this example is responsible for:

- generating deterministic hash positions
- maintaining virtual nodes
- adding physical servers
- removing physical servers
- routing keys
- maintaining sorted ring positions
- handling hash collisions

It is **not** responsible for:

- checking whether a server is alive
- discovering servers
- replicating data
- migrating data
- persisting the ring
- communicating over the network
- deciding server capacity
- retrying failed requests

Keeping these responsibilities separate is important.

A routing algorithm becomes much easier to reason about when it does not also become the entire distributed system.

---

## 4. Deterministic Hashing

Every process using the ring must calculate the same hash for the same input.

For this repository we use SHA-256 and take the first 8 bytes as a 64-bit unsigned integer.

```python
import hashlib


def stable_hash(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(
        digest[:8],
        byteorder="big",
        signed=False,
    )
```

This gives us a stable integer position.

For example:

```text
server:cache-01#replica-0
             |
             v
        stable_hash()
             |
             v
      ring position
```

### Why not Python's `hash()`?

Do not use Python's built-in string hash as the routing protocol for a distributed system.

```python
hash("user-100")
```

Python's string hash seed can vary between processes. Therefore, independent application processes should not rely on the value being identical across process boundaries.

A distributed routing algorithm needs a deterministic hashing contract.

---

## 5. The Ring Data Structures

We need two important structures.

### Ring map

```python
_ring: dict[int, str]
```

This maps:

```text
hash position -> physical server
```

Example:

```text
1000 -> cache-01
2500 -> cache-02
5000 -> cache-03
```

### Sorted positions

```python
_sorted_positions: list[int]
```

Example:

```text
[1000, 2500, 5000]
```

The sorted list lets us perform binary search.

For a key position of `3000`:

```text
1000       2500       5000
 |           |           |
 +-----------+-----------+
                 ^
              key = 3000

next position = 5000
```

Therefore the key belongs to the server stored at position `5000`.

---

## 6. Virtual Nodes

A physical server gets multiple positions on the ring.

Suppose:

```text
virtual_nodes = 3
```

For `cache-01` we create:

```text
server:cache-01#replica-0
server:cache-01#replica-1
server:cache-01#replica-2
```

Each string gets a different hash position.

Conceptually:

```text
                  cache-01
              /      |      \\
          vnode-0  vnode-1  vnode-2
```

This spreads one physical server across the ring instead of giving it only one position.

Virtual nodes primarily help with **distribution**.

They do not magically solve every redistribution problem. Key movement still depends on the exact ring topology and membership change.

---

## 7. Adding a Server

When a server is added:

```text
add_server("cache-05")
```

we create its virtual nodes:

```text
cache-05#replica-0
cache-05#replica-1
...
cache-05#replica-99
```

Each virtual node is hashed and inserted into the ring.

After insertion, the sorted position list is rebuilt.

For this educational implementation:

```text
Add server
   |
   +--> create N virtual nodes
   |
   +--> hash each node
   |
   +--> insert positions
   |
   +--> sort positions
```

The simple implementation sorts the complete list after an update because clarity is more important here than micro-optimizing membership changes.

---

## 8. Removing a Server

Removing a physical server means removing every virtual node owned by that server.

```text
remove_server("cache-03")
```

Conceptually:

```text
cache-03
   |
   +-- vnode-0 -> remove
   +-- vnode-1 -> remove
   +-- vnode-2 -> remove
   +-- ...
   +-- vnode-99 -> remove
```

Then the remaining positions form the new ring.

Keys that previously belonged to `cache-03` move to the next available server clockwise.

Other keys generally remain where they were.

That locality is the main benefit of consistent hashing.

---

## 9. Routing a Key

Suppose the ring contains:

```text
1000 -> cache-01
2500 -> cache-02
5000 -> cache-03
8000 -> cache-04
```

A key hashes to:

```text
4200
```

Binary search finds the first ring position greater than or equal to `4200`:

```text
1000  2500  5000  8000
              ^
            4200
```

The owner is:

```text
cache-03
```

If the key hashes beyond the last ring position:

```text
9000
```

we wrap around to the first position:

```text
9000 -> 1000 -> cache-01
```

This is the circular property of the hash ring.

---

## 10. Binary Search

A naive implementation could scan every ring position:

```python
for position in positions:
    ...
```

That is unnecessarily expensive as the ring grows.

Instead we use Python's `bisect_left`:

```python
from bisect import bisect_left

index = bisect_left(positions, key_position)
```

This gives us the first position greater than or equal to the key position.

The lookup complexity is approximately:

```text
O(log R)
```

where `R` is the number of virtual-node positions.

---

## 11. Complete Implementation

The following implementation is intentionally self-contained.

You can copy it into an example file and run it directly.

```python
from __future__ import annotations

import hashlib
from bisect import bisect_left
from dataclasses import dataclass, field


MAX_HASH = 2**64


def stable_hash(value: str) -> int:
    """Return a deterministic 64-bit integer hash."""
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(
        digest[:8],
        byteorder="big",
        signed=False,
    )


@dataclass
class ConsistentHashRing:
    """A small, reusable consistent-hashing ring with virtual nodes."""

    virtual_nodes: int = 100
    _ring: dict[int, str] = field(default_factory=dict, init=False)
    _sorted_positions: list[int] = field(default_factory=list, init=False)
    _servers: set[str] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        if self.virtual_nodes < 1:
            raise ValueError("virtual_nodes must be at least 1")

    def add_server(self, server: str) -> None:
        """Add a physical server to the ring."""
        if not server:
            raise ValueError("server must not be empty")

        if server in self._servers:
            return

        self._servers.add(server)

        for replica in range(self.virtual_nodes):
            node_id = f"server:{server}#replica-{replica}"
            position = stable_hash(node_id)

            # Extremely unlikely with 64-bit positions, but explicit
            # collision handling keeps the ring deterministic.
            collision_counter = 0

            while position in self._ring:
                collision_counter += 1
                collision_node_id = (
                    f"{node_id}#collision-{collision_counter}"
                )
                position = stable_hash(collision_node_id)

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
            for position, owner in self._ring.items()
            if owner == server
        ]

        for position in positions_to_remove:
            del self._ring[position]

        positions_to_remove_set = set(positions_to_remove)

        self._sorted_positions = [
            position
            for position in self._sorted_positions
            if position not in positions_to_remove_set
        ]

    def get_server(self, key: str) -> str:
        """Return the physical server responsible for a key."""
        if not self._sorted_positions:
            raise RuntimeError("cannot route key: no servers are available")

        key_position = stable_hash(f"key:{key}")

        index = bisect_left(
            self._sorted_positions,
            key_position,
        )

        # Wrap around the ring when the key is after the final position.
        if index == len(self._sorted_positions):
            index = 0

        return self._ring[self._sorted_positions[index]]

    @property
    def servers(self) -> list[str]:
        """Return the physical servers currently in the ring."""
        return sorted(self._servers)

    @property
    def ring_size(self) -> int:
        """Return the number of virtual-node positions."""
        return len(self._sorted_positions)

    def distribution(self, keys: list[str]) -> dict[str, int]:
        """Return how many supplied keys are routed to each server."""
        result = {server: 0 for server in self._servers}

        for key in keys:
            server = self.get_server(key)
            result[server] += 1

        return result


def main() -> None:
    ring = ConsistentHashRing(virtual_nodes=100)

    for server in [
        "cache-01",
        "cache-02",
        "cache-03",
        "cache-04",
    ]:
        ring.add_server(server)

    print("Servers:", ring.servers)
    print("Ring positions:", ring.ring_size)

    keys = [
        "user-100",
        "user-101",
        "user-102",
        "user-103",
        "user-104",
    ]

    print("\nInitial routing:")
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

    print("\nDistribution:")
    sample_keys = [f"user-{i}" for i in range(10_000)]
    print(ring.distribution(sample_keys))


if __name__ == "__main__":
    main()
```

---

## 12. Running the Example

Save the implementation as:

```text
examples/07_production_ready_consistent_hashing.py
```

Then run:

```bash
python examples/07_production_ready_consistent_hashing.py
```

No third-party dependencies are required.

---

## 13. Example Output

The exact routing values depend on the implementation and hash positions, but the output will look similar to:

```text
Servers: ['cache-01', 'cache-02', 'cache-03', 'cache-04']
Ring positions: 400

Initial routing:
user-100 -> cache-03
user-101 -> cache-01
user-102 -> cache-04
user-103 -> cache-02
user-104 -> cache-03

After adding cache-05:
user-100 -> cache-03
user-101 -> cache-05
user-102 -> cache-04
user-103 -> cache-02
user-104 -> cache-03

After removing cache-03:
user-100 -> cache-05
user-101 -> cache-05
user-102 -> cache-04
user-103 -> cache-02
user-104 -> cache-05

Distribution:
{'cache-01': 1982, 'cache-02': 2017, 'cache-04': 2941, 'cache-05': 3060}
```

The exact numbers are not the important part.

The important behavior is that adding or removing one server does **not** cause every key to move.

---

## 14. Why `distribution()` Is Useful

A consistent hash ring can be logically correct while still producing poor distribution.

For example, suppose we route 10,000 keys:

```text
cache-01 -> 2,480
cache-02 -> 2,510
cache-03 -> 2,430
cache-04 -> 2,580
```

This is reasonably balanced.

But if we get:

```text
cache-01 -> 4,800
cache-02 -> 1,700
cache-03 -> 1,900
cache-04 -> 1,600
```

the algorithm is still functioning, but the ring distribution is poor.

Virtual nodes exist partly to reduce this kind of imbalance.

The `distribution()` method gives us a simple way to measure that behavior.

---

## 15. Important Distinction: Distribution vs Movement

These two measurements answer different questions.

### Distribution

> How evenly are keys spread across servers?

Example:

```text
A -> 25%
B -> 24%
C -> 26%
D -> 25%
```

### Movement

> How many existing keys changed owners after a topology change?

Example:

```text
Before: 100,000 keys
After adding one server: 20,000 keys moved
Movement = 20%
```

A ring can have good distribution but still move a meaningful number of keys when membership changes.

Likewise, an implementation can preserve many existing owners while producing an uneven distribution.

Production evaluation should measure both.

---

## 16. Why Virtual Nodes Are Configurable

The implementation exposes:

```python
ConsistentHashRing(virtual_nodes=100)
```

This is intentional.

There is no universally correct value.

For example:

```text
10 virtual nodes/server
100 virtual nodes/server
500 virtual nodes/server
1000 virtual nodes/server
```

Higher values generally provide more sampling of the hash space, which can improve distribution.

But they also increase:

- memory usage
- ring construction time
- membership-update work
- number of positions that must be maintained

Therefore:

> More virtual nodes is not automatically better.

The right value depends on the number of servers, traffic pattern, key distribution, capacity differences, and acceptable memory/update cost.

---

## 17. Weighted Servers

Real systems do not always have equal-capacity servers.

Suppose:

```text
cache-01 = 4 CPU
cache-02 = 4 CPU
cache-03 = 8 CPU
```

Treating all three servers identically may not be ideal.

A simple weighted strategy is to give the larger server more virtual nodes.

For example:

```text
cache-01 -> 100 virtual nodes
cache-02 -> 100 virtual nodes
cache-03 -> 200 virtual nodes
```

Conceptually:

```text
Capacity
   |
   v
Virtual-node count
   |
   v
Expected ownership
```

This is a useful extension, but it should be introduced only when capacity differences are real.

Do not add weighted routing just because it sounds more advanced.

---

## 18. Failure Handling Is Still Outside This Class

This class can tell us:

```text
key -> cache-03
```

It cannot tell us:

```text
Is cache-03 alive?
```

A production system may have a separate membership layer:

```text
Health checks
     |
     v
Membership state
     |
     v
Consistent hash ring
     |
     v
Key routing
```

If `cache-03` fails:

```text
health check detects failure
          |
          v
membership removes cache-03
          |
          v
ring is updated
          |
          v
new requests use the new owner
```

This separation keeps the hashing algorithm simple.

---

## 19. Ring Updates and Concurrency

A real application may have many threads or processes reading the ring while another component updates membership.

For example:

```text
Request 1 ---> read ring
Request 2 ---> read ring
Request 3 ---> read ring
                   ^
                   |
              membership update
```

A production implementation must define how readers observe updates.

One common design is to build a new immutable ring snapshot and then replace the active reference atomically.

Conceptually:

```text
Current ring
    |
    | build update
    v
New ring snapshot
    |
    | atomic swap
    v
Current ring
```

Readers then use either the old complete snapshot or the new complete snapshot rather than observing a partially updated structure.

The exact concurrency mechanism depends on the language, runtime, and deployment model.

This repository keeps that concern outside the basic class so the hashing algorithm remains easy to understand.

---

## 20. Data Migration Is a Separate Concern

One of the most common misunderstandings is:

> Consistent hashing moves the data automatically.

It does not.

Suppose:

```text
user-123 -> cache-03
```

After removing `cache-03`:

```text
user-123 -> cache-04
```

The ring only changed the routing decision.

If `user-123` was actually stored on `cache-03`, something else must decide what happens to that data.

Possible strategies include:

- cache miss and recomputation
- background migration
- replication
- lazy rehydration
- application-level fallback

Therefore:

```text
Consistent hashing
        !=
Data migration
```

This distinction becomes extremely important in real distributed systems.

---

## 21. Replication Is Also Separate

Consistent hashing normally answers:

> Which server owns this key?

A replicated system may need:

```text
Primary
Replica 1
Replica 2
```

A common extension is to walk clockwise around the ring and select additional distinct physical servers.

For example:

```text
key
 |
 v
primary -> cache-03
             |
             v
        replica -> cache-04
             |
             v
        replica -> cache-01
```

That is a separate policy from basic ownership.

The ring gives us the ordered topology. Replication defines how many owners we select from that topology.

---

## 22. Empty Ring Behavior

The implementation explicitly rejects routing when no server exists:

```python
if not self._sorted_positions:
    raise RuntimeError("cannot route key: no servers are available")
```

This is preferable to returning an invalid server or silently hiding the configuration problem.

Example:

```python
ring = ConsistentHashRing()
ring.get_server("user-100")
```

Result:

```text
RuntimeError
```

The caller can then decide how the application should handle the situation.

---

## 23. Duplicate Server Handling

Adding the same server twice should not create another set of virtual nodes.

The implementation therefore treats:

```python
ring.add_server("cache-01")
ring.add_server("cache-01")
```

as one membership entry.

This prevents accidental ring duplication.

Similarly, removing a server that is already absent is a no-op.

These behaviors make the API easier to use safely.

---

## 24. Hash Collisions

The ring uses 64-bit positions.

A collision is possible mathematically, although it is extremely unlikely for the scale of this educational implementation.

Instead of ignoring the possibility, the implementation explicitly handles it:

```python
while position in self._ring:
    collision_counter += 1
    collision_node_id = (
        f"{node_id}#collision-{collision_counter}"
    )
    position = stable_hash(collision_node_id)
```

This makes the behavior deterministic and avoids overwriting an existing ring position.

The important engineering lesson is not that collisions are likely.

It is:

> If a hash collision would corrupt routing state, define the collision behavior explicitly.

---

## 25. Complexity

Let:

```text
N = physical servers
V = virtual nodes per server
R = N × V
```

Then the ring contains approximately:

```text
R positions
```

### Lookup

Binary search:

```text
O(log R)
```

### Add server

For `V` virtual nodes:

```text
O(V)
```

for generating positions, plus sorting work in this simple implementation:

```text
O(R log R)
```

in the worst case when the complete position list is sorted again.

### Remove server

The simple implementation scans the ring to find the server's positions:

```text
O(R)
```

and then rebuilds the sorted list.

A more optimized production implementation could maintain additional indexes for faster membership updates.

But that optimization is intentionally not introduced yet.

---

## 26. Why We Are Not Optimizing Everything Yet

It is tempting to immediately build:

```text
Tree structure
Custom memory layout
Lock-free reads
Distributed membership
Weighted nodes
Replication
Persistence
Health checking
Background migration
```

That would make the repository harder to understand.

The current goal is to establish a correct routing primitive first.

A good engineering sequence is:

```text
Correctness
   ↓
Measurement
   ↓
Identify bottleneck
   ↓
Optimize bottleneck
   ↓
Measure again
```

Not:

```text
Add every optimization first
   ↓
Hope it is faster
```

---

## 27. What This Implementation Gives Us

At this point the repository has a reusable consistent-hashing component that supports:

```text
                    +------------------+
                    | Consistent Hash  |
                    |      Ring        |
                    +------------------+
                       |      |      |
                       v      v      v
                     Add    Remove  Lookup
                       |      |      |
                       +------+------+ 
                              |
                              v
                       Virtual Nodes
                              |
                              v
                       Sorted Hash Ring
```

The core routing contract is now clear:

```text
same key + same ring
        |
        v
same server
```

And when membership changes:

```text
small topology change
        |
        v
localized key movement
```

rather than:

```text
server count changes
        |
        v
almost every key moves
```

---

## 28. Production Architecture Around the Ring

A realistic system can be thought of as several separate layers:

```text
                  +----------------------+
                  |   Service Discovery  |
                  +----------+-----------+
                             |
                             v
                  +----------------------+
                  | Membership / Health  |
                  +----------+-----------+
                             |
                             v
                  +----------------------+
                  | Consistent Hash Ring |
                  +----------+-----------+
                             |
                    +--------+--------+
                    |        |        |
                    v        v        v
                  Node A   Node B   Node C
```

Then, depending on the system:

```text
                 Consistent Hash Ring
                          |
              +-----------+-----------+
              |                       |
              v                       v
          Primary                 Replicas
              |                       |
              +-----------+-----------+
                          |
                          v
                    Data / Cache
```

This separation is more important than making the ring class itself extremely sophisticated.

---

## 29. Testing Strategy

Before using this component as a foundation for other examples, test the important invariants.

### Test 1: Same key is deterministic

```text
same ring
same key
    |
    v
same server
```

### Test 2: Duplicate server does not duplicate membership

```text
add A
add A
```

Expected:

```text
A exists once
```

### Test 3: Removing a server removes its ownership

After:

```python
ring.remove_server("cache-02")
```

no key should be returned as owned by `cache-02`.

### Test 4: Empty ring fails clearly

Routing without servers should raise an explicit error.

### Test 5: Ring size matches membership

For:

```text
4 servers
100 virtual nodes/server
```

expected ring size:

```text
400
```

assuming no collisions require additional positions.

### Test 6: Distribution can be measured

Use a sufficiently large deterministic key set and inspect the ownership counts.

### Test 7: Topology changes are localized

Compare ownership before and after adding or removing one server.

This is one of the most important behavioral tests for consistent hashing.

---

## 30. A Useful Test Pattern for Key Movement

The basic pattern is:

```python
before = {
    key: ring.get_server(key)
    for key in keys
}

ring.add_server("cache-05")

after = {
    key: ring.get_server(key)
    for key in keys
}

moved = sum(
    before[key] != after[key]
    for key in keys
)

movement_ratio = moved / len(keys)
```

This lets us turn a theoretical property into a measurable result.

For example:

```text
100,000 keys

Moved: 20,500

Movement ratio: 20.5%
```

The exact result depends on the ring and hash function.

The important thing is that we measure rather than assume.

---

## 31. One Important Production Caveat

The implementation in this repository uses SHA-256 because it is:

- deterministic
- widely available
- easy to explain
- stable across environments

But SHA-256 is not automatically the best performance choice for every production workload.

If hashing becomes a significant part of the routing latency, a production system may choose a faster deterministic non-cryptographic hash.

The decision should be based on:

```text
Required determinism
Hash quality
Collision behavior
Performance
Language/runtime support
Security requirements
```

Do not optimize the hash function before measuring it in the actual workload.

---

## 32. What We Have Built vs What a Real System Still Needs

| Capability | This implementation | Real production system |
|---|---|---|
| Deterministic hashing | Yes | Yes |
| Virtual nodes | Yes | Usually |
| Add server | Yes | Yes |
| Remove server | Yes | Yes |
| Key lookup | Yes | Yes |
| Binary search | Yes | Usually |
| Distribution measurement | Yes | Yes |
| Health checking | No | Separate component |
| Service discovery | No | Separate component |
| Replication | No | System-specific |
| Data migration | No | System-specific |
| Persistent membership | No | Usually |
| Ring versioning | Concept only | Usually useful |
| Atomic ring updates | Not implemented | Important |
| Weighted capacity | Not implemented | Sometimes |
| Multi-process coordination | No | Required depending on architecture |

This distinction prevents the common mistake of assuming that implementing a hash ring means the distributed-system problem is finished.

---

## 33. Final Mental Model

The entire concept can now be reduced to four steps:

```text
1. Hash servers onto a circular space

2. Hash each key onto the same space

3. Walk clockwise to find the first server position

4. Use virtual nodes to improve distribution
```

When membership changes:

```text
Add/remove server
       |
       v
Only nearby ring ownership changes
       |
       v
Most existing keys keep their owner
```

That is the core reason consistent hashing is useful.

---

## 34. Key Takeaways

1. **Consistent hashing is a routing/partitioning technique, not a complete distributed system.**

2. **Deterministic hashing is mandatory.** Every participant must calculate compatible positions.

3. **Virtual nodes improve distribution**, especially when a small number of physical servers would otherwise create large ownership ranges.

4. **Distribution and key movement are different metrics.** Both should be measured.

5. **Membership and failure detection are separate concerns.** A ring cannot know whether a server is alive by itself.

6. **Ownership is not data migration.** Changing the routing decision does not move existing data automatically.

7. **Replication is a separate policy.** The ring can provide topology; the system decides how many owners are required.

8. **Binary search keeps lookup efficient.** The routing path is approximately `O(log R)` where `R` is the number of ring positions.

9. **More virtual nodes are not automatically better.** They trade memory and update cost for better sampling of the hash space.

10. **Measure before optimizing.** Keep the routing primitive simple until a real bottleneck is identified.

---

## 35. Next Step

The next useful step is to turn the implementation into a proper tested example with:

```text
examples/
    production_ready_consistent_hashing.py

tests/
    test_consistent_hashing.py
```

The tests should verify:

- deterministic routing
- add/remove behavior
- duplicate server handling
- empty-ring behavior
- virtual-node counts
- key distribution
- key movement after topology changes
- server ownership invariants

That gives the repository a clean transition from **understanding the algorithm** to **building a reusable, testable component**.
