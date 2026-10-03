# Basic Consistent Hashing Implementation in Python

In the previous document, we learned how consistent hashing places servers and keys in the same logical hash space.

The routing rule is:

1. Hash each server to get its position on the ring.
2. Hash each key into the same space.
3. Find the first server position at or clockwise after the key position.
4. If no server position is large enough, wrap around to the first server.

This document turns that idea into a small, runnable Python implementation.

We will deliberately keep the first version simple:

- One ring position per server
- A stable hash function
- Sorted server positions
- Clockwise lookup with wrap-around
- A small demonstration showing how assignments behave when a server is added

We will introduce virtual nodes separately after the basic implementation is clear.

---

## 1. Project Structure

From the repository root, create the following file:

```text
consistent-hashing-python/
├── docs/
│   └── 05_basic_consistent_hashing_implementation.md
└── examples/
    └── 03_basic_consistent_hashing.py
```

If your repository already has other documentation and examples, keep them. Add only the new files.

---

## 2. Implementation Overview

The implementation needs to solve three small problems.

### A. Generate a stable hash

Python's built-in `hash()` for strings can produce different values in different processes. For distributed routing, all application instances need to calculate the same ring positions.

We will use SHA-256 from Python's standard library and convert part of its digest into an integer.

### B. Store server positions in sorted order

The ring is represented as a sorted list of hash positions and a mapping from each position to its server identifier.

For example:

```text
Position   Server
-----------------
120        cache-01
430        cache-02
780        cache-03
```

The values above are illustrative. The program calculates the actual positions from server identifiers.

### C. Find the next server clockwise

For a key position, find the first server position greater than or equal to it.

If the key position is greater than every server position, wrap around to the first position.

Python's `bisect` module gives us an efficient way to find the insertion point in a sorted list.

---

## 3. Complete Python Implementation

Create:

```text
examples/03_basic_consistent_hashing.py
```

Copy the entire code below into that file.

```python
import hashlib
from bisect import bisect_left


def stable_hash(value: str) -> int:
    """
    Convert a string into a stable, non-negative integer hash.

    SHA-256 is available in Python's standard library and produces
    consistent results for the same input.
    """
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


class ConsistentHashRing:
    """
    Basic consistent hash ring with one position per server.

    This first version is intentionally small. Virtual nodes,
    replication, and distributed membership management are outside
    its scope.
    """

    def __init__(self) -> None:
        self._ring: dict[int, str] = {}
        self._sorted_positions: list[int] = []

    def add_server(self, server: str) -> None:
        """
        Add a server to the ring.

        A server identifier must be unique. If two different server
        identifiers hash to the same position, this basic version
        raises an error rather than silently overwriting a server.
        """
        if not server:
            raise ValueError("server identifier must not be empty")

        position = stable_hash(f"server:{server}")

        if position in self._ring:
            existing_server = self._ring[position]

            if existing_server == server:
                return

            raise ValueError(
                "Hash collision: "
                f"{server!r} and {existing_server!r} "
                f"map to ring position {position}"
            )

        self._ring[position] = server
        self._sorted_positions.insert(
            bisect_left(self._sorted_positions, position),
            position,
        )

    def remove_server(self, server: str) -> None:
        """
        Remove a server from the ring.

        Raises ValueError if the server is not currently present.
        """
        matching_positions = [
            position
            for position, existing_server in self._ring.items()
            if existing_server == server
        ]

        if not matching_positions:
            raise ValueError(f"Server {server!r} is not in the ring")

        for position in matching_positions:
            del self._ring[position]
            index = bisect_left(self._sorted_positions, position)

            if (
                index >= len(self._sorted_positions)
                or self._sorted_positions[index] != position
            ):
                raise RuntimeError("Ring index is inconsistent")

            self._sorted_positions.pop(index)

    def get_server(self, key: str) -> str:
        """
        Return the first server clockwise from the key's ring position.

        If the key position is after the final server position,
        wrap around to the first server position.
        """
        if not key:
            raise ValueError("key must not be empty")

        if not self._sorted_positions:
            raise ValueError("Cannot route a key: the ring is empty")

        key_position = stable_hash(f"key:{key}")

        index = bisect_left(self._sorted_positions, key_position)

        if index == len(self._sorted_positions):
            index = 0

        server_position = self._sorted_positions[index]
        return self._ring[server_position]

    def servers(self) -> list[str]:
        """
        Return server identifiers in ring-position order.
        """
        return [
            self._ring[position]
            for position in self._sorted_positions
        ]

    def __len__(self) -> int:
        """
        Return the number of servers currently on the ring.
        """
        return len(self._ring)


def main() -> None:
    ring = ConsistentHashRing()

    initial_servers = [
        "cache-01",
        "cache-02",
        "cache-03",
    ]

    keys = [
        "user:1001",
        "user:1002",
        "user:1003",
        "user:1004",
        "user:1005",
        "product:2001",
        "product:2002",
        "session:abc",
        "session:def",
        "cart:5001",
    ]

    for server in initial_servers:
        ring.add_server(server)

    print("CONSISTENT HASHING: BASIC RING")
    print("=" * 55)
    print("Servers in ring order:")
    for server in ring.servers():
        print(f"  {server}")

    print("\nKey assignments before adding a server:")
    before = {}

    for key in keys:
        server = ring.get_server(key)
        before[key] = server
        print(f"  {key:16} -> {server}")

    new_server = "cache-04"
    ring.add_server(new_server)

    print(f"\nKey assignments after adding {new_server}:")
    after = {}

    for key in keys:
        server = ring.get_server(key)
        after[key] = server
        print(f"  {key:16} -> {server}")

    moved_keys = [
        key for key in keys
        if before[key] != after[key]
    ]

    print("\nRedistribution summary:")
    print("-" * 55)
    print(f"Total keys : {len(keys)}")
    print(f"Moved keys : {len(moved_keys)}")
    print(
        "Moved keys are those whose server assignment changed "
        "after adding the new server."
    )

    print("\nKeys that changed servers:")
    if moved_keys:
        for key in moved_keys:
            print(
                f"  {key:16} "
                f"{before[key]} -> {after[key]}"
            )
    else:
        print("  None in this sample")


if __name__ == "__main__":
    main()
```

---

## 4. Run the Program

Run this command from the repository root:

```bash
python examples/03_basic_consistent_hashing.py
```

The program will:

1. Create a ring with three servers.
2. Assign sample keys to servers.
3. Add a fourth server.
4. Assign the same keys again.
5. Report which assignments changed.

The exact server assignments depend on the stable hash values produced by the code, but they should remain consistent across separate runs using the same code and server identifiers.

---

## 5. Understand the Ring Data Structures

The implementation uses two data structures:

```python
self._ring: dict[int, str] = {}
self._sorted_positions: list[int] = []
```

The dictionary maps a ring position to a server:

```text
ring position -> server identifier
```

The sorted list lets us find the next server clockwise:

```text
[120, 430, 780, ...]
```

The numbers here are only illustrative.

We need both structures because the dictionary is convenient for retrieving a server by position, while the sorted list is convenient for locating the next position.

When a server is added, we calculate its position, store the mapping, and insert the position in sorted order.

When a server is removed, we delete its mapping and remove its position from the sorted list.

---

## 6. How `bisect_left` Helps

The line:

```python
index = bisect_left(self._sorted_positions, key_position)
```

returns the insertion index where `key_position` could be placed while preserving the sorted order.

For example:

```text
Server positions: [120, 430, 780]
Key position:          500
```

The insertion point is before `780`, so the next server clockwise is the server at position `780`.

Another example:

```text
Server positions: [120, 430, 780]
Key position:          900
```

There is no server position at or after `900`. The insertion index equals the length of the list, so the implementation wraps around to index `0`, selecting the server at position `120`.

This implements the ring's clockwise lookup rule.

---

## 7. Why the Hash Input Has a Prefix

Notice that the implementation hashes:

```python
stable_hash(f"server:{server}")
```

for servers, and:

```python
stable_hash(f"key:{key}")
```

for keys.

The prefixes separate the two input namespaces. A server identifier and a key with the same text should not automatically be treated as the same ring object.

The prefix is not a substitute for choosing unique server identifiers. It simply makes the intended distinction explicit.

All application instances using this ring must use the same prefixes, encoding, and hash function.

---

## 8. What Happens When We Add a Server?

Initially, the ring contains:

```text
cache-01
cache-02
cache-03
```

The program calculates a ring position for each server. Each key is assigned to the first server clockwise from its own position.

When `cache-04` is added, it receives a new ring position. In the basic ring model, the new server takes over the portion of the ring between its predecessor and its own position.

Only keys in that ownership range should change their assigned server. Other keys should retain their existing assignments.

The demonstration compares the assignments before and after the addition to show which sample keys changed owners.

A small sample may not show a smooth distribution. With only a few keys and one position per server, results can look uneven. We will address the distribution limitation when we introduce virtual nodes.

---

## 9. What Happens When We Remove a Server?

The class also supports server removal:

```python
ring.remove_server("cache-02")
```

Removing a server deletes its ring position. Keys that previously mapped to that server will now map to the next server clockwise, including wrap-around when necessary.

You can experiment by adding this snippet after the existing demonstration logic or by writing a small separate script:

```python
ring.remove_server("cache-02")

for key in keys:
    print(f"{key} -> {ring.get_server(key)}")
```

Do not remove a server before taking the initial assignments if you want to compare movement before and after the removal.

---

## 10. Important Limitation: One Position Per Server

This version intentionally assigns only one ring position to each server.

That makes the code easier to understand, but it can create uneven ownership ranges.

For example, one server might own a large section of the ring while another owns a small section. As a result, the number of keys assigned to each server may be unbalanced.

Consistent hashing reduces redistribution during membership changes; it does not automatically guarantee equal key distribution.

A common improvement is to give each physical server multiple ring positions, called **virtual nodes**. We will add them in a later implementation and measure how they affect distribution.

---

## 11. Complexity and Trade-offs

Let \(S\) be the number of servers and \(K\) be the number of keys.

### Lookup

Finding the next server uses binary search over the sorted positions:

\[
O(\log S)
\]

The hash calculation itself depends on the length of the input string.

### Adding a server

Finding the insertion point is \(O(\log S)\), but inserting into a Python list may shift later elements, making the list insertion \(O(S)\).

### Removing a server

This implementation searches for the server and removes its ring position. The simple search and list update are \(O(S)\).

These costs are reasonable for an educational implementation and modest server counts. A production implementation may use different structures or optimized ring-management techniques if membership changes or ring sizes justify them.

---

## 12. What This Implementation Does Not Do

This is a routing demonstration, not a production distributed cache.

It does not:

- Connect to Redis or a database.
- Move real key-value data between servers.
- Replicate keys across multiple servers.
- Detect server failures.
- Synchronize ring membership between application instances.
- Account for different server capacities.
- Use virtual nodes.
- Guarantee balanced request traffic.
- Coordinate safe data migration during membership changes.

These concerns are intentionally excluded so we can understand the core algorithm first.

---

## 13. Key Takeaways

- Servers and keys are mapped into the same logical hash space.
- Server positions are stored in sorted order.
- A key maps to the first server clockwise from its ring position.
- If the key lies after the final server position, lookup wraps around to the first position.
- A stable hash function helps separate application instances calculate the same mapping.
- Adding or removing a server changes ownership for only a portion of the ring in the basic model.
- One position per server can produce uneven ownership ranges.
- Virtual nodes are the next improvement to explore.

## Next

In the next document, we will extend this implementation with **virtual nodes**. We will compare key distribution across physical servers and explain why multiple ring positions per server usually provide a more balanced assignment.
