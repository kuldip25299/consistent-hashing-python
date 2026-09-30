# Consistent Hashing in Python — Scaling Distributed Systems with Minimal Data Movement

A practical, from-scratch implementation of **Consistent Hashing in Python**.

This repository explains why simple modulo-based distribution becomes a problem when servers are added or removed, how a consistent hash ring solves the key redistribution problem, how virtual nodes improve distribution, and where Consistent Hashing fits in real-world distributed systems.

The goal is not just to implement a hash ring, but to understand **why the problem exists, how the algorithm solves it, and what trade-offs appear in production systems**.

---

## Why This Repository?

When an application grows, a single server may no longer be enough.

For example, imagine a distributed cache:

```text
                    Users
                      |
                      v
                Application
                      |
          -------------------------
          |           |           |
          v           v           v
       Cache A     Cache B     Cache C
```

Millions of users generate millions of keys:

```text
user:1001
user:1002
user:1003
user:1004
...
```

Those keys need to be distributed across multiple cache servers.

A simple approach is:

```python
server_index = hash(key) % number_of_servers
```

At first, this looks reasonable.

With 3 servers:

```text
hash(key) % 3
```

But what happens when a fourth server is added?

```text
hash(key) % 4
```

A large number of keys can now map to different servers.

That means previously cached data may suddenly be looked up on another server.

The result can be:

```text
More cache misses
       ↓
More database queries
       ↓
Higher database load
       ↓
Higher application latency
```

This repository explores that problem and introduces **Consistent Hashing** as one way to reduce unnecessary key movement when the server topology changes.

---

# What You Will Learn

By completing this repository, you will understand:

- Why distributed systems need key-to-node mapping
- How modulo hashing distributes keys
- Why `hash(key) % N` becomes a problem when `N` changes
- How to measure key redistribution
- What a hash ring is
- How keys are mapped onto a consistent hash ring
- How nodes are placed on the ring
- How adding a node affects existing keys
- How removing a node affects existing keys
- Why Consistent Hashing reduces data movement
- Why virtual nodes are needed
- How virtual nodes improve distribution
- How to measure distribution imbalance
- Where Consistent Hashing is useful
- When Consistent Hashing may not be the right approach
- How Consistent Hashing differs from other partitioning techniques
- What additional concerns are required in production systems

---

# Core Idea

The fundamental difference is how the keyspace is partitioned.

## Modulo Hashing

With modulo hashing:

```text
Key
 |
 v
hash(key)
 |
 v
% number_of_servers
 |
 v
Server
```

Changing the number of servers changes the modulo operation.

For example:

```text
3 servers:

hash(key) % 3
```

becomes:

```text
4 servers:

hash(key) % 4
```

Many keys therefore receive a different destination.

---

## Consistent Hashing

Consistent Hashing maps both:

- Servers
- Keys

onto the same logical hash space.

Conceptually:

```text
                 Server B
                    ●
              .-----------.
           .-'             '-.
         .'                   '.
        /                       \
       |                         |
Server A ●                       ● Server C
       |                         |
        \                       /
         '.                   .'
           '-.             .-'
              '-----------'
```

The hash space behaves like a ring.

A key is hashed onto the ring:

```text
User Key
   |
   v
hash(key)
   |
   v
Position on Ring
   |
   v
Next Server Clockwise
```

When a new server is added, only a portion of the keys need to move.

This is the central idea behind Consistent Hashing.

---

# Repository Goals

This project intentionally keeps the implementation simple.

We are not building a distributed database or cache system.

Instead, we are building the core routing mechanism that helps us understand:

```text
Key
 ↓
Hash
 ↓
Ring
 ↓
Node
```

The implementation uses Python's standard library.

There will be:

- No Redis
- No database
- No external distributed system
- No framework
- No cloud dependency

The focus is the algorithm and the system-design reasoning behind it.

---

# Learning Flow

The repository follows this progression:

```text
Business Problem
      ↓
Naive Modulo Hashing
      ↓
Measure Key Redistribution
      ↓
Consistent Hashing Concept
      ↓
Basic Hash Ring
      ↓
Node Addition / Removal
      ↓
Virtual Nodes
      ↓
Distribution Analysis
      ↓
Real-World Use Cases
      ↓
Alternatives
      ↓
Production Trade-offs
```

Each step builds on the previous one.

---

# Repository Structure

```text
consistent-hashing-python/
│
├── README.md
│
├── docs/
│   ├── 01_business_problem.md
│   ├── 02_naive_modulo_hashing.md
│   ├── 03_measuring_key_redistribution.md
│   ├── 04_how_consistent_hashing_works.md
│   ├── 05_basic_hash_ring.md
│   ├── 06_node_addition_and_removal.md
│   ├── 07_virtual_nodes.md
│   ├── 08_distribution_and_rebalancing.md
│   ├── 09_real_world_use_cases.md
│   ├── 10_consistent_hashing_vs_alternatives.md
│   └── 11_production_considerations.md
│
├── examples/
│   ├── 01_naive_modulo_hashing.py
│   ├── 02_measure_key_redistribution.py
│   ├── 03_basic_consistent_hashing.py
│   ├── 04_add_remove_nodes.py
│   └── 05_virtual_nodes_and_distribution.py
│
├── consistent_hashing/
│   ├── __init__.py
│   └── ring.py
│
├── tests/
│   └── test_ring.py
│
└── requirements.txt
```

---

# 1. The Business Problem

The repository starts with a practical distributed-system problem.

Imagine an application serving millions of users.

A cache initially has three servers:

```text
              Application
                   |
        -----------------------
        |          |          |
        v          v          v
     Cache A    Cache B    Cache C
```

The application needs to determine which cache server owns a key.

For example:

```text
user:1001 → Cache A
user:1002 → Cache C
user:1003 → Cache B
user:1004 → Cache A
```

The routing decision should be:

- deterministic
- fast
- distributed
- scalable

The problem becomes more interesting when the infrastructure changes.

For example:

```text
Before:

Cache A
Cache B
Cache C
```

Then the system scales:

```text
After:

Cache A
Cache B
Cache C
Cache D
```

The routing algorithm must now determine what happens to existing keys.

This is where the limitations of naive hashing become visible.

See:

```text
docs/01_business_problem.md
```

---

# 2. Naive Modulo Hashing

The simplest solution is:

```python
server_index = hash(key) % number_of_servers
```

For example:

```text
Servers:

0 → Cache A
1 → Cache B
2 → Cache C
```

A key might be mapped as:

```text
hash("user:1001") % 3 = 1

user:1001 → Cache B
```

This works well while the number of servers remains stable.

But when the number changes:

```text
hash(key) % 3
```

becomes:

```text
hash(key) % 4
```

The mapping can change for a large portion of keys.

The repository will first implement this simple approach so we can see the problem rather than jumping directly to Consistent Hashing.

See:

```text
docs/02_naive_modulo_hashing.md
```

---

# 3. Measuring Key Redistribution

Instead of simply saying:

> Many keys will move.

we will measure it.

For example:

```text
Number of keys: 100,000

Initial servers:
A
B
C

New servers:
A
B
C
D
```

We can calculate:

```text
Keys before
    ↓
Key → Server

Keys after
    ↓
Key → Server

Compare
    ↓
How many keys changed?
```

This gives us a concrete measurement of the redistribution problem.

We will measure:

- number of moved keys
- percentage of moved keys
- keys remaining on the same node
- effect of adding a node
- effect of removing a node

See:

```text
docs/03_measuring_key_redistribution.md
```

and:

```text
examples/02_measure_key_redistribution.py
```

---

# 4. How Consistent Hashing Works

Now we introduce the main concept.

Instead of calculating:

```text
hash(key) % number_of_servers
```

we create a logical hash space.

Conceptually:

```text
                    0
              .-----------.
           .-'             '-.
        .-'                   '-.
       /                         \
      |                           |
      |                           |
      |                           |
       \                         /
        '-.                   .-'
           '-.             .-'
              '-----------'
```

The beginning and end of the hash space connect.

Therefore:

```text
Hash Space → Ring
```

Both nodes and keys are hashed into this same space.

For example:

```text
Cache A → position 100
Cache B → position 250
Cache C → position 700
```

Then:

```text
user:1001 → position 180
```

The key moves clockwise until it finds its owning node:

```text
user:1001
    |
    v
position 180
    |
    | clockwise
    v
Cache B
```

The number of servers no longer directly determines the key's position.

That is the important conceptual change.

See:

```text
docs/04_how_consistent_hashing_works.md
```

---

# 5. Basic Hash Ring Implementation

We then implement the concept in Python.

The basic API will look like:

```python
from consistent_hashing import ConsistentHashRing

ring = ConsistentHashRing()

ring.add_node("cache-a")
ring.add_node("cache-b")
ring.add_node("cache-c")

server = ring.get_node("user:123")

print(server)
```

Conceptually:

```text
             Hash Ring

          Cache A
             ●
       .-----------.
     .'             '.
    /                 \
   |                   |
   |       key         |
   |        ●          |
    \                 /
     '.             .'
       '-----------'
             ●
          Cache B
```

The implementation will demonstrate:

- hashing nodes
- hashing keys
- storing ring positions
- finding the next node
- handling ring wrap-around
- adding nodes
- removing nodes

See:

```text
docs/05_basic_hash_ring.md
```

and:

```text
consistent_hashing/ring.py
```

---

# 6. Adding and Removing Nodes

Distributed systems change continuously.

Servers may be:

- added
- removed
- replaced
- scaled horizontally
- taken out for maintenance

We will demonstrate what happens when a node changes.

Example:

```text
Before:

A -------- B -------- C
```

Add node D:

```text
Before:

A -------- B -------- C


After:

A ---- B ---- D ---- C
```

Only keys belonging to the affected range need to change ownership.

Similarly, when a node is removed:

```text
A ---- B ---- D ---- C
           X
```

The keys owned by D move to another node according to the ring.

See:

```text
docs/06_node_addition_and_removal.md
```

and:

```text
examples/04_add_remove_nodes.py
```

---

# 7. Virtual Nodes

A basic ring can still have a distribution problem.

Suppose three physical servers are placed at:

```text
A → 10
B → 20
C → 900
```

The ring is not evenly distributed.

One server may own a much larger portion of the hash space than another.

That can create an imbalance such as:

```text
A → 5% of keys
B → 10% of keys
C → 85% of keys
```

Virtual nodes solve this by giving each physical server multiple positions on the ring.

Instead of:

```text
A → 1 position
B → 1 position
C → 1 position
```

we can have:

```text
A → 100 virtual positions
B → 100 virtual positions
C → 100 virtual positions
```

Conceptually:

```text
A-1
A-2
A-3
...
A-100

B-1
B-2
...
B-100

C-1
C-2
...
C-100
```

These virtual positions are distributed around the ring.

The physical server therefore owns multiple smaller ranges instead of one large range.

See:

```text
docs/07_virtual_nodes.md
```

and:

```text
examples/05_virtual_nodes_and_distribution.py
```

---

# 8. Distribution and Rebalancing

A distributed system should not only minimize key movement.

It should also distribute keys reasonably evenly.

We will measure:

```text
Keys per node
```

and:

```text
Minimum keys
Maximum keys
Average keys
```

We can compare:

```text
Modulo Hashing
```

against:

```text
Consistent Hashing
```

and:

```text
Consistent Hashing + Virtual Nodes
```

We will also measure redistribution when nodes are added or removed.

The goal is to understand the trade-off between:

```text
Distribution
        +
Minimal movement
        +
Implementation complexity
```

See:

```text
docs/08_distribution_and_rebalancing.md
```

---

# 9. Real-World Use Cases

Consistent Hashing is a general distributed-system technique.

It can be useful in systems where keys need to be mapped to changing sets of nodes.

## Distributed Caches

```text
User Key
   ↓
Hash Ring
   ↓
Cache Node
```

A common reason is reducing unnecessary cache movement when nodes change.

---

## Database Sharding

A logical key can be mapped to a shard:

```text
customer_id
     ↓
hash
     ↓
partition
```

The exact partitioning strategy depends on the database and workload.

---

## Distributed Object Storage

Objects can be distributed across storage nodes using hashed identifiers.

```text
object_id
    ↓
hash
    ↓
storage node
```

---

## Distributed Workers

Work items can be assigned to workers based on a stable key:

```text
customer_id
    ↓
hash
    ↓
worker
```

This can help maintain affinity for related work.

---

## Session or Data Routing

A logical identifier can be mapped to a service instance or partition.

```text
session_id
    ↓
hash
    ↓
server
```

The exact architecture depends on whether sessions are local, replicated, or stored externally.

---

## CDN / Edge Systems

Hash-based routing can also be used as part of distributed content or request-routing strategies.

The exact implementation depends on the architecture and workload.

The important point is that Consistent Hashing is not a complete architecture by itself.

It is a **partitioning and routing technique** that can be used inside larger systems.

See:

```text
docs/09_real_world_use_cases.md
```

---

# 10. Consistent Hashing vs Alternatives

Consistent Hashing is not the only way to distribute keys.

We will compare it with other approaches.

## Modulo Hashing

```text
hash(key) % N
```

Advantages:

- extremely simple
- very fast
- easy to understand

Limitation:

- changing `N` can cause substantial key redistribution

---

## Consistent Hashing

```text
hash(key)
    ↓
ring
    ↓
next node
```

Advantages:

- reduces movement when nodes change
- supports dynamic node membership
- works well with virtual nodes

Trade-offs:

- more implementation complexity
- ring management
- distribution requires careful configuration

---

## Rendezvous Hashing

Another approach is to calculate a score for each node and select the node with the highest score.

Conceptually:

```text
key
 ↓
score(key, node A)
score(key, node B)
score(key, node C)
 ↓
highest score
 ↓
selected node
```

It can provide stable mappings without explicitly using a ring.

---

## Range Partitioning

Another strategy is to assign ranges:

```text
A → 0 - 999
B → 1000 - 1999
C → 2000 - 2999
```

This can work well when ordered or range queries matter.

However, workload distribution and rebalancing characteristics differ from hash-based partitioning.

See:

```text
docs/10_consistent_hashing_vs_alternatives.md
```

---

# 11. Production Considerations

A hash ring solves one specific problem:

> How should keys be mapped to nodes while minimizing unnecessary movement when the node set changes?

It does **not** automatically solve every distributed-system problem.

Production systems may additionally need:

- node health checking
- failure detection
- replication
- data durability
- consistency guarantees
- hot-key handling
- service discovery
- ring synchronization
- rebalancing
- persistence
- concurrency control
- weighted nodes
- monitoring
- operational tooling

For example:

```text
Consistent Hashing
        |
        +---- Key placement
        |
        +---- Node membership
        |
        +---- Reduced movement
```

But:

```text
Replication
Durability
Failover
Consistency
Recovery
```

must be designed separately.

This distinction is important.

**Consistent Hashing is a building block, not a complete distributed system.**

See:

```text
docs/11_production_considerations.md
```

---

# Python Implementation

The main implementation is intentionally small.

The expected usage is:

```python
from consistent_hashing import ConsistentHashRing

ring = ConsistentHashRing()

ring.add_node("cache-a")
ring.add_node("cache-b")
ring.add_node("cache-c")

print(ring.get_node("user:1001"))
print(ring.get_node("user:1002"))
print(ring.get_node("user:1003"))
```

Virtual nodes can later be enabled:

```python
ring = ConsistentHashRing(virtual_nodes=100)

ring.add_node("cache-a")
ring.add_node("cache-b")
ring.add_node("cache-c")
```

The implementation will remain focused on the core algorithm rather than trying to reproduce a production distributed cache.

---

# Running the Examples

Clone the repository:

```bash
git clone https://github.com/kuldip25299/consistent-hashing-python.git
```

Move into the project:

```bash
cd consistent-hashing-python
```

Create a virtual environment if desired:

```bash
python3 -m venv venv
```

Activate it on macOS/Linux:

```bash
source venv/bin/activate
```

Activate it on Windows:

```powershell
venv\Scripts\activate
```

There are no third-party dependencies required.

---

## Run the Examples

### 1. Naive Modulo Hashing

```bash
python examples/01_naive_modulo_hashing.py
```

### 2. Measure Key Redistribution

```bash
python examples/02_measure_key_redistribution.py
```

### 3. Basic Consistent Hashing

```bash
python examples/03_basic_consistent_hashing.py
```

### 4. Add and Remove Nodes

```bash
python examples/04_add_remove_nodes.py
```

### 5. Virtual Nodes and Distribution

```bash
python examples/05_virtual_nodes_and_distribution.py
```

---

# Running Tests

Run all tests with:

```bash
python -m unittest discover -s tests -v
```

The tests will cover the core behavior of the hash ring, including:

- node addition
- node removal
- key lookup
- deterministic mapping
- ring wrap-around
- virtual nodes
- invalid configuration
- empty ring behavior

---

# Requirements

The project intentionally uses the Python standard library.

No external dependencies are required.

```text
Python 3.9+
```

---

# What This Project Does Not Try to Build

This repository is intentionally focused.

It does **not** attempt to build:

- a distributed cache
- a distributed database
- a service discovery system
- a replication protocol
- a consensus algorithm
- a fault-tolerant storage system
- a production-grade distributed framework

Instead, the project focuses on one important distributed-systems primitive:

```text
Consistent Hashing
```

The objective is to understand the algorithm deeply enough to recognize where it fits in a larger architecture.

---

# Key Takeaways

After completing this repository, the main mental model should be:

```text
                 Distributed System
                         |
                         v
                  Many Nodes
                         |
                         v
                 Need Key Routing
                         |
              ----------------------
              |                    |
              v                    v
       Modulo Hashing       Consistent Hashing
              |                    |
              v                    v
       Node count changes     Hash Ring
              |                    |
              v                    v
      Many keys move       Fewer keys move
                                   |
                                   v
                           Virtual Nodes
                                   |
                                   v
                         Better distribution
```

The most important lesson is not simply:

> Consistent Hashing uses a ring.

The deeper lesson is:

> **When a distributed system changes its number of nodes, the way keys are partitioned determines how much existing data needs to move.**

That is the scalability problem this repository is designed to make visible.

---

# Project Learning Path

Recommended order:

```text
01. Business Problem
        ↓
02. Naive Modulo Hashing
        ↓
03. Measure Key Redistribution
        ↓
04. How Consistent Hashing Works
        ↓
05. Basic Hash Ring
        ↓
06. Node Addition and Removal
        ↓
07. Virtual Nodes
        ↓
08. Distribution and Rebalancing
        ↓
09. Real-World Use Cases
        ↓
10. Alternatives
        ↓
11. Production Considerations
```

**Do not skip the modulo-hashing section.**

Understanding why the naive approach breaks makes the value of Consistent Hashing much easier to understand.

---

# Final Architecture

At the end of the repository, the core architecture is intentionally simple:

```text
                   Application
                       |
                       |
                     Key
                       |
                       v
               Consistent Hash
                       |
                       v
                  Hash Ring
                       |
          +------------+------------+
          |            |            |
          v            v            v
       Node A        Node B       Node C
```

With virtual nodes:

```text
                    Hash Ring
                        |
        --------------------------------
        |       |       |       |      |
        A-1     B-1     C-1     A-2    B-2
        |       |       |       |      |
        +-------+-------+-------+------+
                        |
                  Physical Nodes
                        |
                +-------+-------+
                |       |       |
                A       B       C
```

This gives us a simple foundation for understanding how distributed systems can partition keys while reducing unnecessary movement during scaling events.

---

# Repository Philosophy

This project follows a simple principle:

```text
Don't start with the algorithm.
Start with the problem.
```

First understand:

```text
Why does key redistribution matter?
```

Then:

```text
Why does modulo hashing create the problem?
```

Then:

```text
How does Consistent Hashing reduce it?
```

And finally:

```text
What additional problems appear in production?
```

The implementation exists to make those concepts measurable and runnable, not just theoretical.

---

## License

This project is intended for learning, experimentation, and understanding distributed-system concepts.
