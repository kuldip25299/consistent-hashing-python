# Consistent Hashing with Python

A practical, runnable guide to understanding consistent hashing: why modulo-based routing causes widespread key movement, how a hash ring reduces redistribution, how virtual nodes improve distribution, and which production concerns remain outside the hashing algorithm itself.

The repository follows a progression from **business problem → baseline → measurement → implementation → production trade-offs**. The examples use Python's standard library; no Redis, database, or external service is required.

## Why this project exists

Imagine a service routing user sessions, cache keys, or customer records across several servers. A common baseline is:

```python
server = hash(key) % number_of_servers
```

This is simple, but adding or removing a server changes the modulo result for many keys. That can cause a large amount of cache churn or data movement.

Consistent hashing maps servers and keys into the same hash space. A key is assigned to the first server position clockwise from the key's position. When membership changes, only the keys in the affected ring ranges should move.

Consistent hashing reduces unnecessary reassignment; it does **not** by itself provide service discovery, failure detection, replication, data migration, or durable storage.

## Repository structure

```text
consistent-hashing-python/
├── docs/
│   ├── 01_business_problem.md
│   ├── 02_naive_modulo_hashing.md
│   ├── 03_measuring_key_redistribution.md
│   ├── 04_how_consistent_hashing_works.md
│   ├── 05_basic_consistent_hashing_implementation.md
│   ├── 06_virtual_nodes.md
│   ├── 07_measuring_key_redistribution.md
│   ├── 08_production_considerations.md
│   └── 09_production_ready_consistent_hashing.md
├── examples/
│   ├── 01_basic_consistent_hashing.py
│   ├── 02_virtual_nodes.py
│   ├── 03_measuring_key_movement.py
│   ├── 04_production_considerations.py
│   ├── 05_production_ready_consistent_hashing.py
│   └── test_consistent_hashing.py
├── .gitignore
└── README.md
```

## Learning path

Read the documentation in order:

1. **Business problem** — understand why changing the server pool can become expensive.
2. **Naive modulo hashing** — build the baseline and understand its redistribution problem.
3. **Measuring key redistribution** — quantify how many keys change owners.
4. **How consistent hashing works** — learn the ring and clockwise lookup.
5. **Basic implementation** — implement a minimal ring.
6. **Virtual nodes** — improve distribution by assigning each physical server multiple ring positions.
7. **Measure key redistribution** — compare approaches with an experiment rather than relying on intuition.
8. **Production considerations** — examine deterministic hashing, membership updates, migration, replication, and operational trade-offs.
9. **Production-ready design** — bring the concepts together and review the boundaries of a reusable implementation.

## Requirements

- Python 3.10 or newer is recommended.
- No third-party packages are required for the examples or unit tests shown here.

Check your Python version:

```bash
python --version
```

## Run the examples

Run commands from the repository root.

### Basic consistent hashing

```bash
python examples/01_basic_consistent_hashing.py
```

### Virtual nodes

```bash
python examples/02_virtual_nodes.py
```

### Measure key movement

```bash
python examples/03_measuring_key_movement.py
```

### Production considerations demonstration

```bash
python examples/04_production_considerations.py
```

### Production-ready implementation demonstration

```bash
python examples/05_production_ready_consistent_hashing.py
```

The commands assume the recommended filenames shown above.

## Run the unit tests

The test file stays in `examples/` as requested. From the repository root, run:

```bash
python -m unittest discover -s examples -p "test_*.py" -v
```

The tests import the production implementation by filename. If you rename `10_production_ready_consistent_hashing.py` to `05_production_ready_consistent_hashing.py`, update the implementation path inside `test_consistent_hashing.py` to match.

## Core ideas demonstrated

### 1. Deterministic hashing

Distributed components must calculate the same hash for the same input. Python's built-in string `hash()` is not appropriate for stable routing across independent processes because its string hash seed can vary between runs. The examples use a stable digest-based hash instead.

### 2. Consistent hashing ring

Both keys and server positions are mapped into a shared hash space. Lookup selects the first server position clockwise from the key's hash, wrapping to the beginning of the ring when necessary.

### 3. Virtual nodes

A physical server can own multiple positions on the ring. Virtual nodes generally improve distribution and reduce imbalance, at the cost of a larger ring and more memory. They do not guarantee perfectly even load.

### 4. Measure instead of guessing

The measurement examples count keys whose assigned server changes after a topology update. Results depend on the hash function, ring positions, server names, and virtual-node count. Treat experiment output as evidence for that specific setup, not a universal benchmark.

### 5. Ownership is not migration

A new ring assignment tells the application where a key should route under the new topology. It does not move the underlying cached or persistent data. Migration, replication, consistency, and handling requests during rebalancing require separate design decisions.

## Complexity

Let `R` be the number of positions on the ring and `K` the number of keys being evaluated.

- Ring lookup with sorted positions and binary search: **O(log R)**.
- A simple implementation that sorts all positions after an insertion can take **O(R log R)** for that update.
- Memory for ring positions: **O(R)**.
- Measuring movement across `K` keys requires routing those keys before and after the topology change, typically **O(K log R)** per routing pass.

Exact update costs depend on the data structure and implementation.

## Important production boundaries

Consistent hashing solves a specific problem: reducing key reassignment when the set of servers changes. It does not automatically solve:

- discovering which servers are available;
- deciding when a server has failed;
- distributing ring changes consistently across application instances;
- migrating data to newly responsible servers;
- replicating keys or surviving loss of a data-bearing node;
- accounting for servers with different capacities;
- protecting against hot keys or uneven request costs;
- managing rollout, rollback, and ring-version compatibility.

These concerns are discussed in `docs/08_production_considerations.md` and `docs/09_production_ready_consistent_hashing.md`.

## Design choices and trade-offs

| Choice | Benefit | Cost or limitation |
|---|---|---|
| Stable digest-based hash | Consistent routing across processes | Digest computation has a cost |
| Virtual nodes | Usually better distribution | More ring positions and memory |
| Binary search over sorted positions | Efficient key lookup | Ring updates must keep positions ordered |
| Rebuild the ring on membership changes | Simple and easy to reason about | Can be costly for very large rings or frequent changes |
| Consistent hashing | Limits reassignment after membership changes | Does not move or replicate the underlying data |

## Suggested experiments

1. Increase the number of keys and measure the percentage that move after adding a server.
2. Compare one position per server with different virtual-node counts.
3. Remove a server and verify that no key routes to it afterward.
4. Change the server names and observe that the ring placement changes.
5. Compare distribution counts across servers; do not assume every server receives the same number of keys.
6. Consider what happens when a server is reachable but overloaded, rather than completely unavailable.

## What this repository is—and is not

This is an educational project designed to make the algorithm and its trade-offs concrete with runnable Python. The implementation examples are not a drop-in distributed storage system or a substitute for production-tested libraries. Before using consistent hashing in a real service, define membership, rollout, migration, replication, failure, and observability behavior for your system.

## Contributing

Suggestions, corrections, alternative implementations, and measured results are welcome. When sharing benchmark results, include the number of keys, server count, hash function, virtual-node count, and topology change so others can reproduce the experiment.

