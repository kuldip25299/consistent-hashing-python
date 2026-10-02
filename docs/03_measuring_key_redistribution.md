# Measuring Key Redistribution

In the previous document, we saw that naive modulo hashing uses:

```python
server_index = hash(key) % number_of_servers
```

The calculation is simple, but changing the number of servers can change the destination of many keys.

In this document, we will measure that behavior instead of relying only on a conceptual example.

We will build a small experiment that compares key assignments before and after a cluster-size change, then calculate:

- Total number of keys
- Number of keys that changed servers
- Percentage of keys that moved

The goal is to establish a measurable baseline before implementing consistent hashing.

---

## 1. What Are We Measuring?

Imagine an application distributes one million keys across three servers.

```text
Before:
Server 0
Server 1
Server 2
```

We then add a fourth server:

```text
After:
Server 0
Server 1
Server 2
Server 3
```

With modulo hashing, the routing rule changes from:

```python
hash(key) % 3
```

to:

```python
hash(key) % 4
```

We want to answer a specific question:

**What percentage of existing keys now maps to a different server?**

For each key, compare its old server with its new server.

```text
Old server == New server  -> Key stayed
Old server != New server  -> Key moved
```

The movement percentage is:

```text
Moved percentage = (Moved keys / Total keys) * 100
```

This metric is useful because it turns a general scaling concern into something we can compare between algorithms.

---

## 2. Make the Experiment Reproducible

Python's built-in `hash()` is not appropriate for this experiment when we want repeatable mappings across separate program runs. String hashes are randomized between processes by default.

Instead, we will use a stable hash function based on `hashlib`.

For a given key, the function will return the same hash value across runs. This means the results can be reproduced and compared after code changes.

We will also use a fixed list of keys generated from integer IDs:

```text
user:0
user:1
user:2
...
```

The keys represent a simplified distributed cache or key-value store. The experiment does not need real user records or a database.

---

## 3. The Algorithm

The experiment follows these steps:

1. Generate a fixed set of keys.
2. Assign every key to a server using modulo hashing with the original server count.
3. Assign the same keys again using the new server count.
4. Compare each key's old and new server.
5. Count how many keys moved.
6. Calculate the movement percentage.
7. Print a summary.

The flow is:

```text
                 Generate keys
                      |
                      v
           Map keys with old server count
                      |
                      v
           Map keys with new server count
                      |
                      v
              Compare assignments
                      |
                      v
             Count moved keys
                      |
                      v
            Calculate percentage
```

---

## 4. Complete Python Implementation

Create this file:

```text
examples/02_measuring_key_redistribution.py
```

Copy the complete code below into that file.

```python
import argparse
import hashlib


def stable_hash(key: str) -> int:
    """
    Return a stable integer hash for a key.

    Unlike Python's built-in hash() for strings, this value remains
    consistent across separate program runs.
    """
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def get_server(key: str, number_of_servers: int) -> int:
    """
    Assign a key to a server using naive modulo hashing.
    """
    if number_of_servers <= 0:
        raise ValueError("number_of_servers must be greater than zero")

    return stable_hash(key) % number_of_servers


def build_mapping(keys: list[str], number_of_servers: int) -> dict[str, int]:
    """
    Build a mapping of each key to its server index.
    """
    return {
        key: get_server(key, number_of_servers)
        for key in keys
    }


def measure_redistribution(
    keys: list[str],
    old_server_count: int,
    new_server_count: int,
) -> dict[str, float | int]:
    """
    Compare modulo-hashing assignments before and after a cluster change.
    """
    if not keys:
        raise ValueError("keys must contain at least one key")

    if old_server_count <= 0 or new_server_count <= 0:
        raise ValueError("server counts must be greater than zero")

    old_mapping = build_mapping(keys, old_server_count)
    new_mapping = build_mapping(keys, new_server_count)

    moved_keys = [
        key
        for key in keys
        if old_mapping[key] != new_mapping[key]
    ]

    total_keys = len(keys)
    moved_count = len(moved_keys)
    stayed_count = total_keys - moved_count
    moved_percentage = (moved_count / total_keys) * 100

    return {
        "total_keys": total_keys,
        "old_server_count": old_server_count,
        "new_server_count": new_server_count,
        "moved_keys": moved_count,
        "stayed_keys": stayed_count,
        "moved_percentage": moved_percentage,
    }


def print_report(result: dict[str, float | int]) -> None:
    """
    Print the redistribution measurements in a readable format.
    """
    print()
    print("=" * 58)
    print("NAIVE MODULO HASHING: KEY REDISTRIBUTION")
    print("=" * 58)
    print(f"Total keys          : {result['total_keys']:,}")
    print(f"Servers before      : {result['old_server_count']}")
    print(f"Servers after       : {result['new_server_count']}")
    print("-" * 58)
    print(f"Keys that stayed    : {result['stayed_keys']:,}")
    print(f"Keys that moved     : {result['moved_keys']:,}")
    print(f"Moved percentage    : {result['moved_percentage']:.2f}%")
    print("=" * 58)
    print()
    print(
        "Note: a moved key means the modulo calculation assigns it "
        "to a different server index."
    )
    print(
        "This experiment measures changed assignments; it does not "
        "measure physical data-transfer time or cache-miss latency."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Measure key redistribution when naive modulo hashing "
            "uses a different number of servers."
        )
    )

    parser.add_argument(
        "--keys",
        type=int,
        default=100_000,
        help="Number of keys to generate (default: 100000).",
    )
    parser.add_argument(
        "--old-servers",
        type=int,
        default=3,
        help="Number of servers before the change (default: 3).",
    )
    parser.add_argument(
        "--new-servers",
        type=int,
        default=4,
        help="Number of servers after the change (default: 4).",
    )

    args = parser.parse_args()

    if args.keys <= 0:
        parser.error("--keys must be greater than zero")

    if args.old_servers <= 0:
        parser.error("--old-servers must be greater than zero")

    if args.new_servers <= 0:
        parser.error("--new-servers must be greater than zero")

    return args


def main() -> None:
    args = parse_args()

    keys = [f"user:{index}" for index in range(args.keys)]

    result = measure_redistribution(
        keys=keys,
        old_server_count=args.old_servers,
        new_server_count=args.new_servers,
    )

    print_report(result)


if __name__ == "__main__":
    main()
```

---

## 5. Run the Experiment

Run the default experiment from the repository root:

```bash
python examples/02_measuring_key_redistribution.py
```

The default configuration is:

```text
Keys:           100,000
Servers before: 3
Servers after:  4
```

The script prints a report containing the total number of keys, the number that stayed on the same server index, the number that moved, and the percentage that moved.

The exact percentage is calculated from the stable hash values used by the program. It should not be copied from an illustrative example or assumed to be an exact universal property of modulo hashing.

### Try a larger key set

```bash
python examples/02_measuring_key_redistribution.py \
  --keys 1000000 \
  --old-servers 3 \
  --new-servers 4
```

### Try removing a server

```bash
python examples/02_measuring_key_redistribution.py \
  --keys 100000 \
  --old-servers 4 \
  --new-servers 3
```

### Try changing the cluster by more than one server

```bash
python examples/02_measuring_key_redistribution.py \
  --keys 100000 \
  --old-servers 4 \
  --new-servers 8
```

These experiments help show how assignments change for different cluster sizes.

---

## 6. How to Read the Results

Suppose a report contains:

```text
Total keys          : 100,000
Servers before      : 3
Servers after       : 4
Keys that stayed    : 25,000
Keys that moved     : 75,000
Moved percentage    : 75.00%
```

These numbers are an **illustration of how to read the report**, not a guaranteed output for the supplied hash function.

The interpretation is:

- `100,000` keys were checked.
- `75,000` keys received a different server index.
- `25,000` keys retained the same server index.
- The measured movement percentage is `75%`.

A key is counted as moved if its destination index changes. This is not the same as saying the key's data was physically transferred. Actual data movement depends on how the application stores and migrates its data.

---

## 7. Why the Movement Percentage Matters

In a distributed cache, a changed assignment may cause a cache miss if the new destination does not already contain the key.

In a storage system, a changed assignment may require data to be moved or made available at a new location.

The operational chain can look like this:

```text
Cluster membership changes
          |
          v
Key assignments change
          |
          v
Cache misses or data movement
          |
          v
Additional backend work
          |
          v
Potential increase in latency
```

The experiment measures the second step: **how many assignments change**.

It does not directly measure database load, cache hit rate, network traffic, or latency. Those depend on the architecture and workload.

This distinction matters when interpreting benchmarks: a high movement percentage signals potential operational work, but it is not itself a measurement of production impact.

---

## 8. A Useful Mathematical Baseline

Assume the hash values distribute keys uniformly across a sufficiently large keyspace.

For a key to remain assigned to the same numeric server index when changing from \(N\) servers to \(M\) servers, its hash value must satisfy:

```text
hash(key) % N == hash(key) % M
```

For the special case where the server count changes from \(N\) to \(N+1\), the number of possible residue pairs is constrained by both divisors. Under a uniform distribution of residues modulo the least common multiple, the probability of retaining the same index is:

\[
P(\text{stay}) = \frac{\gcd(N,M)}{\max(N,M)}
\]

Therefore, the expected movement fraction for this idealized model is:

\[
P(\text{move}) = 1 - \frac{\gcd(N,M)}{\max(N,M)}
\]

For example, moving from 3 servers to 4:

\[
P(\text{move}) = 1 - \frac{1}{4} = 75\%
\]

This is an expected value under the stated uniform-residue model. A finite set of keys can produce a slightly different measured percentage.

For server counts where one divides the other, the same-index retention behavior can differ. The formula makes that dependence explicit rather than assuming that every cluster-size change produces the same movement percentage.

---

## 9. What Happens When the Server Count Doubles?

Consider a change from four servers to eight servers.

The routing rule changes from:

```python
stable_hash(key) % 4
```

to:

```python
stable_hash(key) % 8
```

Under the uniform-residue model:

\[
P(\text{stay}) = \frac{\gcd(4,8)}{8} = \frac{4}{8} = 50\%
\]

So the expected fraction of keys whose numeric server index remains the same is 50%, and the expected fraction that changes is 50%.

This does not mean that every key moves to a newly added server. Some keys move between existing server indices, and some retain their index. The important point is that the modulo mapping is recalculated across the entire key set.

Run the command to measure the actual result for our deterministic test keys:

```bash
python examples/02_measuring_key_redistribution.py \
  --keys 100000 \
  --old-servers 4 \
  --new-servers 8
```

---

## 10. Important Limitation of This Experiment

This program uses a stable hash function and generated keys so the comparison is reproducible.

However, it is still a simplified experiment:

- It treats all keys equally.
- It assumes server indices represent server identities.
- It does not model unequal server capacity.
- It does not model replicas or replication factors.
- It does not move any actual data.
- It does not simulate cache expiration, warm-up, or traffic patterns.
- It measures changed assignments, not request latency.

The experiment is designed to isolate one property: **how modulo-based key assignment responds to a change in server count**.

We will use the same idea of measuring moved keys when we introduce consistent hashing, so the comparison stays focused on redistribution.

---

## 11. Why Consistent Hashing Is the Next Step

Naive modulo hashing makes the number of servers part of every key's assignment:

```python
server_index = stable_hash(key) % number_of_servers
```

When the number changes, the assignment rule changes for the entire keyspace.

Consistent hashing takes a different approach: it places servers and keys on a logical hash ring. Adding or removing a server changes only a portion of the ring's ownership ranges, so ideally only a smaller portion of keys needs to move.

Consistent hashing does not eliminate all redistribution. It aims to limit how much redistribution is necessary when cluster membership changes.

Before implementing it, we now have a baseline metric:

```text
Moved percentage = moved keys / total keys * 100
```

We can compare this metric across approaches rather than judging an algorithm only by how simple its code looks.

---

## Key Takeaways

1. A server-count change can alter many assignments under modulo hashing.
2. Stable hashing makes the experiment reproducible across program runs.
3. The movement percentage is the number of changed assignments divided by the total number of keys.
4. Assignment changes may lead to cache misses or data movement, but the experiment does not measure those downstream effects.
5. Redistribution depends on the old and new server counts; it should be measured rather than assumed.
6. This measurement becomes a useful baseline for evaluating consistent hashing.

## Next

In the next document, we will introduce the core idea behind consistent hashing and explain how a logical hash ring helps reduce key redistribution when servers are added or removed.
