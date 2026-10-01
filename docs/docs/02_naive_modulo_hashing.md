# Naive Modulo Hashing

Before understanding consistent hashing, we first need to understand a very common approach used to distribute keys across multiple servers.

A simple strategy is:

```text
hash(key) % number_of_servers
```

This approach is easy to understand and easy to implement.

It can work well when the number of servers is stable.

The problem appears when servers are added or removed.

A small infrastructure change can cause a large number of keys to move to different servers.

That key redistribution can create cache misses, database pressure, and latency spikes.

This document builds the idea step by step.

---

## 1. The Basic Problem

Suppose we have three servers:

```text
Server 0
Server 1
Server 2
```

We want to distribute application keys across these servers.

For example:

```text
user:1001
user:1002
user:1003
user:1004
user:1005
```

A simple way to choose a server is:

```python
server_index = hash(key) % number_of_servers
```

If there are three servers:

```python
server_index = hash(key) % 3
```

The result will always be one of:

```text
0
1
2
```

So the key can be assigned to:

```text
0 -> Server 0
1 -> Server 1
2 -> Server 2
```

---

# 2. How Modulo Hashing Works

The algorithm has only a few steps.

```text
             Key
              |
              v
        Hash the key
              |
              v
       hash(key) % N
              |
              v
       Server index
```

Where:

```text
N = number of servers
```

For three servers:

```text
hash(key) % 3
```

For five servers:

```text
hash(key) % 5
```

For ten servers:

```text
hash(key) % 10
```

The number of servers directly affects the calculation.

That detail is the main weakness of this approach.

---

# 3. Simple Python Implementation

Let's start with the smallest possible implementation.

```python
def get_server(key, number_of_servers):
    server_index = hash(key) % number_of_servers
    return server_index


servers = 3

keys = [
    "user:1001",
    "user:1002",
    "user:1003",
    "user:1004",
    "user:1005",
]

for key in keys:
    server = get_server(key, servers)
    print(f"{key} -> Server {server}")
```

A possible output could look like:

```text
user:1001 -> Server 1
user:1002 -> Server 0
user:1003 -> Server 2
user:1004 -> Server 1
user:1005 -> Server 0
```

The exact output of Python's built-in `hash()` can vary between processes, so the important part is the distribution logic rather than these exact server numbers.

---

# 4. Why Hashing Is Used

A hash function converts a key into a numeric value.

Conceptually:

```text
"user:1001"
     |
     v
  hash()
     |
     v
  183746281
```

Another key produces another hash value:

```text
"user:1002"
     |
     v
  hash()
     |
     v
  918273645
```

We then use modulo to convert the large hash value into a server index.

For example:

```text
183746281 % 3 = 1
```

Therefore:

```text
"user:1001" -> Server 1
```

The hash function gives us a deterministic mapping for a given process, and modulo converts that result into the available server range.

---

# 5. Example With Fixed Hash Values

To understand the algorithm without depending on Python's built-in hash behavior, we can use fixed hash values.

Consider:

```text
Key       Hash Value
--------------------
A         10
B         11
C         12
D         13
E         14
F         15
```

With three servers:

```text
hash(key) % 3
```

We get:

```text
A -> 10 % 3 -> 1
B -> 11 % 3 -> 2
C -> 12 % 3 -> 0
D -> 13 % 3 -> 1
E -> 14 % 3 -> 2
F -> 15 % 3 -> 0
```

Therefore:

```text
Server 0:
    C
    F

Server 1:
    A
    D

Server 2:
    B
    E
```

The mapping is simple and deterministic.

---

# 6. Key Distribution

One of the main goals of hashing is to distribute keys across servers.

Suppose we have:

```text
3 servers
1000 keys
```

Ideally, we would get approximately:

```text
Server 0 -> ~333 keys
Server 1 -> ~333 keys
Server 2 -> ~334 keys
```

A good hash function generally gives a reasonably distributed set of hash values.

However, this does not guarantee perfectly equal distribution.

The actual distribution depends on:

* the hash function
* the input keys
* the number of keys
* the number of servers

For large enough key sets, a good hash function generally gives an approximately balanced distribution.

---

# 7. The Important Part: Number of Servers

Now consider the formula again:

```python
hash(key) % number_of_servers
```

The number of servers is part of the mapping.

With three servers:

```python
hash(key) % 3
```

With four servers:

```python
hash(key) % 4
```

These are completely different calculations.

This means changing the number of servers can change the destination of many keys.

That is the core problem with naive modulo hashing.

---

# 8. Adding a New Server

Suppose our system initially has:

```text
Server 0
Server 1
Server 2
```

Therefore:

```text
number_of_servers = 3
```

We calculate:

```text
hash(key) % 3
```

Now suppose we add another server:

```text
Server 0
Server 1
Server 2
Server 3
```

The formula becomes:

```text
hash(key) % 4
```

Notice what changed:

```text
Before:

hash(key) % 3


After:

hash(key) % 4
```

Even though the key itself did not change, the calculation changed.

Therefore the destination server can change.

---

# 9. Example of Remapping

Let's use fixed hash values.

Suppose:

```text
Key       Hash
----------------
A         10
B         11
C         12
D         13
E         14
F         15
```

With three servers:

```text
hash % 3
```

We get:

```text
A -> 10 % 3 -> Server 1
B -> 11 % 3 -> Server 2
C -> 12 % 3 -> Server 0
D -> 13 % 3 -> Server 1
E -> 14 % 3 -> Server 2
F -> 15 % 3 -> Server 0
```

So:

```text
Server 0 -> C, F
Server 1 -> A, D
Server 2 -> B, E
```

Now add Server 3.

We calculate:

```text
hash % 4
```

The result becomes:

```text
A -> 10 % 4 -> Server 2
B -> 11 % 4 -> Server 3
C -> 12 % 4 -> Server 0
D -> 13 % 4 -> Server 1
E -> 14 % 4 -> Server 2
F -> 15 % 4 -> Server 3
```

Now compare the mappings.

| Key | Before: 3 Servers | After: 4 Servers |
| --- | ----------------- | ---------------- |
| A   | Server 1          | Server 2         |
| B   | Server 2          | Server 3         |
| C   | Server 0          | Server 0         |
| D   | Server 1          | Server 1         |
| E   | Server 2          | Server 2         |
| F   | Server 0          | Server 3         |

Several keys moved.

The important observation is:

```text
Adding one server
        |
        v
number_of_servers changes
        |
        v
Modulo calculation changes
        |
        v
Many keys get new destinations
```

---

# 10. Why Remapping Is Expensive

At first glance, changing a server assignment may not seem like a serious problem.

But consider a real distributed system.

Suppose we have:

```text
10 million cache keys
```

distributed across:

```text
10 cache servers
```

Now we add:

```text
Server 11
```

The formula changes from:

```text
hash(key) % 10
```

to:

```text
hash(key) % 11
```

A large number of keys can now point to different servers.

The application may still be able to calculate the new destination instantly.

The problem is what happens to the data stored at the old destination.

---

# 11. Cache Misses

Consider a distributed cache.

Initially:

```text
"user:1001" -> Server 2
```

The application stores:

```text
Server 2:
    user:1001 -> user data
```

Later, a new server is added.

After recalculating:

```text
"user:1001" -> Server 5
```

The application asks Server 5:

```text
GET user:1001
```

But Server 5 may not contain the key.

The result is:

```text
CACHE MISS
```

The application may then need to retrieve the data from the database.

For example:

```text
Application
    |
    v
Server 5
    |
    | cache miss
    v
Database
```

The database now receives additional traffic.

---

# 12. Database Pressure

A cache is often used to reduce database load.

The normal flow may be:

```text
Application
     |
     v
Cache
     |
     | hit
     v
Return data
```

When many keys are remapped:

```text
Application
     |
     v
New cache server
     |
     | miss
     v
Database
```

If a large percentage of cached keys suddenly miss, database traffic can increase significantly.

For example:

```text
Normal:

1,000,000 requests
    |
    +-- 950,000 cache hits
    |
    +-- 50,000 database requests
```

After significant remapping:

```text
1,000,000 requests
    |
    +-- many cache misses
    |
    +-- large increase in database requests
```

This can create a chain reaction:

```text
Server change
     |
     v
Key remapping
     |
     v
Cache misses
     |
     v
More database requests
     |
     v
Higher database load
     |
     v
Higher latency
```

In a heavily loaded production system, this can become a serious scaling problem.

---

# 13. Data Movement

The problem becomes even more important when the distributed system requires actual data movement.

Imagine a distributed storage system:

```text
Server 0
Server 1
Server 2
```

Keys are distributed using:

```text
hash(key) % 3
```

If Server 3 is added, the new calculation becomes:

```text
hash(key) % 4
```

Keys that now belong to different servers may need to be copied or moved.

Conceptually:

```text
Before:

Server 0 -> A, D
Server 1 -> B, E
Server 2 -> C, F


After:

Server 0 -> A
Server 1 -> C
Server 2 -> B
Server 3 -> D, E, F
```

The exact movement depends on the hash values.

The important issue is that changing the server count can affect a large portion of the keyspace.

---

# 14. Server Removal Has the Same Problem

The problem is not limited to adding servers.

Suppose we have:

```text
4 servers
```

and one server fails or is removed.

The calculation changes from:

```text
hash(key) % 4
```

to:

```text
hash(key) % 3
```

Again, many keys can map to different servers.

Therefore:

```text
Server addition
        |
        v
Key remapping
```

and:

```text
Server removal
        |
        v
Key remapping
```

Both can cause significant redistribution.

---

# 15. Simple Experiment

We can demonstrate the problem using Python.

Create:

```text
examples/01_naive_modulo_hashing.py
```

with:

```python
def get_server(key, number_of_servers):
    return hash(key) % number_of_servers


keys = [f"user:{i}" for i in range(20)]

servers_before = 3
servers_after = 4

print("Key mapping before adding a server:")
print("-" * 40)

before = {}

for key in keys:
    server = get_server(key, servers_before)
    before[key] = server
    print(f"{key:10} -> Server {server}")


print("\nKey mapping after adding a server:")
print("-" * 40)

after = {}

for key in keys:
    server = get_server(key, servers_after)
    after[key] = server
    print(f"{key:10} -> Server {server}")


print("\nKeys that changed servers:")
print("-" * 40)

moved_keys = 0

for key in keys:
    if before[key] != after[key]:
        moved_keys += 1
        print(
            f"{key:10} "
            f"Server {before[key]} -> Server {after[key]}"
        )


print("\nSummary")
print("-" * 40)
print(f"Total keys : {len(keys)}")
print(f"Moved keys : {moved_keys}")
print(
    f"Moved percentage : "
    f"{(moved_keys / len(keys)) * 100:.2f}%"
)
```

Run it with:

```bash
python examples/01_naive_modulo_hashing.py
```

Because Python's built-in `hash()` can vary between processes, the exact mapping can differ between runs.

The experiment is intended to demonstrate the important behavior:

```text
Changing the number of servers
        |
        v
Changes modulo divisor
        |
        v
Changes key-to-server mapping
```

---

# 16. Measuring Redistribution

Instead of only looking at individual keys, we can measure how much of the keyspace moves.

For example:

```text
Total keys = 1,000,000

Before:
3 servers

After:
4 servers
```

We calculate:

```text
moved_keys / total_keys
```

and convert it to a percentage.

For example:

```text
Moved keys = 750,000
Total keys = 1,000,000

Redistribution = 75%
```

The exact percentage depends on the hash distribution and the server counts.

The important system-design question is not:

> Can we calculate the new server?

We can.

The more important question is:

> How many existing keys are affected when the cluster changes?

That is where naive modulo hashing becomes problematic.

---

# 17. The Main Strength of Modulo Hashing

Despite the problem, modulo hashing has an important advantage:

**It is extremely simple.**

The routing logic is essentially:

```python
server = hash(key) % number_of_servers
```

There is:

* no hash ring
* no virtual nodes
* no metadata structure
* no complex routing algorithm
* very little computation

For a stable number of servers, this can be perfectly reasonable.

---

# 18. When Naive Modulo Hashing Can Work

Modulo hashing can be useful when:

### 1. The number of servers rarely changes

If the cluster size is stable, there may be little redistribution.

### 2. The data is cheap to recreate

If a cache miss only requires inexpensive recomputation, remapping may be acceptable.

### 3. The system is small

For a small internal application, simplicity may be more valuable than sophisticated distribution.

### 4. The system does not require persistent ownership

If data can safely be recreated or fetched from another source, moving keys may not be expensive.

### 5. Controlled environments

Some systems know their server count in advance and rarely change it.

The key point is that modulo hashing is not inherently "bad."

Its weakness becomes important when the server count changes frequently or when moving/remissing data is expensive.

---

# 19. The System Design Trade-off

Modulo hashing gives us:

```text
Simple routing
+
Low implementation complexity
+
Fast calculation
```

But we pay for it when the cluster changes:

```text
Server count changes
        |
        v
Large key redistribution
        |
        +--> Cache misses
        |
        +--> Data movement
        |
        +--> Database pressure
        |
        +--> Latency spikes
```

This is a classic system-design trade-off.

The algorithm is simple.

The operational consequences can be expensive.

---

# 20. A More Formal View

Let:

```text
H(k) = hash value of key k
N    = number of servers
```

The server assignment is:

```text
S(k) = H(k) mod N
```

If the number of servers changes from:

```text
N
```

to:

```text
N + 1
```

the assignment becomes:

```text
S'(k) = H(k) mod (N + 1)
```

In general:

```text
S(k) != S'(k)
```

for many keys.

Therefore, changing `N` changes the mapping function itself.

This is the mathematical reason behind the redistribution problem.

---

# 21. Why This Matters in Distributed Systems

In a single-server application, changing a server count is not usually a key-routing problem.

In a distributed system, the server itself may own some portion of the data.

For example:

```text
                    Application
                         |
          +--------------+--------------+
          |              |              |
          v              v              v
      Server 0       Server 1       Server 2
          |              |              |
       Keys A-D       Keys E-H       Keys I-L
```

The application needs a deterministic way to know where a key belongs.

Modulo hashing provides that.

But when the cluster changes:

```text
Server 0
Server 1
Server 2
Server 3   <- new
```

the mapping changes.

That means the routing algorithm is also changing.

This is the fundamental limitation we need to solve.

---

# 22. What We Want From a Better Approach

Ideally, we want a hashing strategy where:

```text
Server added
     |
     v
Only a relatively small portion of keys move
```

and:

```text
Server removed
     |
     v
Only keys associated with that server need significant redistribution
```

We still want:

```text
Fast key lookup
+
Deterministic routing
+
Reasonably balanced distribution
+
Minimal redistribution
```

This leads us to **consistent hashing**.

---

# 23. Modulo Hashing vs. Consistent Hashing

The fundamental difference is how the keyspace is organized.

### Modulo hashing

```text
server = hash(key) % N
```

The number of servers directly determines the mapping.

```text
N changes
  |
  v
Mapping changes
  |
  v
Many keys may move
```

### Consistent hashing

Keys and servers are placed on a logical hash ring.

Conceptually:

```text
             Server A
                |
        +-------+-------+
        |               |
    Server D          Server B
        |               |
        +-------+-------+
                |
             Server C
```

The server count can change without recalculating every key against a completely different modulo divisor.

Instead, only the relevant portion of the ring needs to change.

We will build this concept in the next document.

---

# 24. Key Takeaways

The naive modulo approach is:

```python
hash(key) % number_of_servers
```

It is attractive because it is:

* simple
* fast
* deterministic
* easy to implement

But the mapping depends directly on the number of servers.

When the server count changes:

```text
Add server
   OR
Remove server
```

the modulo divisor changes.

That can cause:

```text
Key remapping
     |
     +--> Cache misses
     |
     +--> Data movement
     |
     +--> Database pressure
     |
     +--> Increased latency
```

So the main problem is not that modulo hashing is slow.

The problem is **how much existing data can be affected when the cluster changes**.

---

# 25. The Bigger System Design Lesson

When evaluating a distributed-system algorithm, we should not only ask:

```text
"Does it work?"
```

We should also ask:

```text
"What happens when the system changes?"
```

For hashing, the important operational questions are:

* What happens when a server is added?
* What happens when a server is removed?
* How many keys move?
* How much data needs to move?
* How many cache misses are created?
* Can the database absorb the additional load?
* Does latency increase during redistribution?
* How much complexity does the solution introduce?

Modulo hashing gives us a very simple answer to the first problem:

```text
hash(key) % N
```

But it exposes a scaling problem when `N` changes.

Understanding this limitation gives us the motivation for consistent hashing.

---

## Next

In the next document:

```text
docs/03_measuring_key_redistribution.md
```

we will measure the actual impact of changing the number of servers.

Instead of only discussing redistribution conceptually, we will use Python to calculate:

```text
Total keys
Moved keys
Moved percentage
```

for different cluster sizes.

That gives us a measurable baseline before introducing consistent hashing.
