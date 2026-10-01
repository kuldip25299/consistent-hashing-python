# Business Problem — Why Do We Need Consistent Hashing?

Before understanding Consistent Hashing, we need to understand the distributed-systems problem it solves.

The problem is not simply:

> "How do we hash a key?"

The real problem is:

> **How do we distribute a large number of keys across multiple servers while keeping the mapping stable when servers are added or removed?**

This problem appears in distributed caches, database sharding, distributed storage, worker routing, and other systems where data or requests need to be assigned to one of many nodes.

---

## 1. A Simple Starting Point

Imagine a web application serving users.

Initially, the application uses a single cache server:

```text
Users
  |
  v
Application
  |
  v
Cache A
```

The application stores frequently accessed data in the cache.

For example:

```text
user:1001
user:1002
user:1003
product:5001
product:5002
order:9001
```

The cache allows the application to avoid repeatedly querying the database.

A simplified request flow looks like:

```text
User Request
     |
     v
Application
     |
     v
Check Cache
     |
     +---- Cache Hit ----> Return Data
     |
     +---- Cache Miss
              |
              v
           Database
              |
              v
        Store in Cache
              |
              v
         Return Data
```

As traffic and data volume grow, a single cache server can eventually become a bottleneck.

At that point, we may want to scale horizontally.

---

## 2. Horizontal Scaling

Instead of continuously making one cache server larger, we can introduce multiple cache servers.

For example:

```text
                    Application
                         |
              -----------------------
              |          |          |
              v          v          v
           Cache A    Cache B    Cache C
```

Now we have three cache servers.

But a new question appears:

> **Which cache server should store a particular key?**

For example:

```text
user:1001 -> ?
user:1002 -> ?
user:1003 -> ?
user:1004 -> ?
```

We need a deterministic routing strategy.

---

## 3. Why Random Routing Does Not Work

One simple idea would be to randomly select a cache server.

For example:

```text
user:1001 -> Cache A
user:1002 -> Cache C
user:1003 -> Cache B
user:1004 -> Cache A
```

But the next request for `user:1001` could randomly go to another server:

```text
user:1001 -> Cache C
```

The data may already exist in Cache A, but Cache C does not have it.

That creates a cache miss even though the application has already cached the data.

Therefore, we need deterministic routing.

For the same key and the same cluster topology, the routing decision should remain stable.

```text
user:1001 -> Cache B
user:1001 -> Cache B
user:1001 -> Cache B
```

This gives us predictable key ownership.

---

## 4. We Need Key-to-Server Mapping

We can think about the problem as:

```text
                 Key
                  |
                  v
          Routing Algorithm
                  |
        +---------+---------+
        |         |         |
        v         v         v
     Cache A   Cache B   Cache C
```

For example:

```text
user:1001 -> Cache B
user:1002 -> Cache A
user:1003 -> Cache C
user:1004 -> Cache B
```

When the same key is requested again, the application should calculate the same destination while the set of available nodes has not changed.

This is the basic requirement.

---

## 5. A Simple Solution: Modulo Hashing

One of the simplest approaches is to hash the key and use the number of servers to select a server.

Conceptually:

```python
server_index = hash(key) % number_of_servers
```

If we have three servers:

```text
0 -> Cache A
1 -> Cache B
2 -> Cache C
```

Then:

```text
hash("user:1001") % 3
```

might produce:

```text
1
```

So:

```text
user:1001 -> Cache B
```

Another key might produce:

```text
hash("user:1002") % 3 = 0
```

So:

```text
user:1002 -> Cache A
```

This approach is simple and fast.

For a fixed set of servers, it can work well.

The problem appears when the number of servers changes.

---

## 6. What Happens When We Add a Server?

Suppose our application currently has:

```text
Cache A
Cache B
Cache C
```

The routing calculation is:

```text
hash(key) % 3
```

Now traffic grows and we add:

```text
Cache D
```

The cluster becomes:

```text
Cache A
Cache B
Cache C
Cache D
```

The routing calculation must now become:

```text
hash(key) % 4
```

That small infrastructure change can have a large effect on the key mapping.

---

## 7. Existing Keys Can Move

Consider:

```text
user:1001
```

Before adding Cache D:

```text
hash("user:1001") % 3
```

might produce:

```text
1
```

Therefore:

```text
user:1001 -> Cache B
```

After adding Cache D:

```text
hash("user:1001") % 4
```

might produce:

```text
3
```

Therefore:

```text
user:1001 -> Cache D
```

The key moved even though the key itself did not change.

The only thing that changed was the number of available servers.

---

## 8. The Problem Multiplies With More Keys

In a real system, we may have millions of keys.

For example:

```text
10,000,000 keys
```

Before scaling:

```text
hash(key) % 3
```

After adding a fourth server:

```text
hash(key) % 4
```

The modulo operation is different for every key.

As a result, many keys can receive a different destination.

The exact number of moved keys depends on the key distribution and hashing behavior, but the important point is:

> **Changing the number of servers can cause a large portion of the keyspace to be remapped.**

Conceptually:

```text
Before:

Key 1 -> A
Key 2 -> B
Key 3 -> C
Key 4 -> A
Key 5 -> C
...


After adding D:

Key 1 -> D
Key 2 -> A
Key 3 -> B
Key 4 -> C
Key 5 -> D
...
```

The entire mapping is effectively recalculated using a different divisor.

---

## 9. Why Is Key Movement a Problem?

This is particularly important for distributed caches.

Suppose:

```text
user:1001 -> Cache B
```

and Cache B contains the cached user data.

After adding Cache D, the routing calculation may produce:

```text
user:1001 -> Cache D
```

If Cache D does not contain the key, the application gets a cache miss.

The request path becomes:

```text
Application
     |
     v
 Cache D
     |
     v
Cache Miss
     |
     v
 Database
     |
     v
Re-populate Cache
```

A single cache miss is not usually a serious problem.

The issue appears when a large number of keys move at the same time.

---

## 10. Database Pressure

Imagine a system with a large amount of cached data.

A topology change causes many existing keys to point to different cache servers.

Those new cache locations may not contain the data.

Therefore:

```text
More Keys Moved
      |
      v
More Cache Misses
      |
      v
More Database Queries
      |
      v
Higher Database Load
      |
      v
Higher Application Latency
```

The cache cluster was scaled to handle more traffic, but the topology change itself can temporarily create additional load on the database.

This is an important distributed-systems problem.

---

## 11. Cache Warm-Up Problem

There is another consequence.

Suppose Cache D is newly added.

Initially, it contains little or none of the existing cached data.

If many keys suddenly start mapping to Cache D, the application may need to populate those keys again.

Conceptually:

```text
New Cache D
     |
     v
Few existing entries
     |
     v
Many requests arrive
     |
     v
Cache Misses
     |
     v
Database Reads
     |
     v
Cache D becomes populated
```

This process is sometimes referred to as cache warm-up.

If the amount of data is large, this can generate significant additional work.

---

## 12. Removing a Server Creates the Same Class of Problem

Adding a node is not the only problem.

Suppose we have:

```text
Cache A
Cache B
Cache C
Cache D
```

and Cache D is removed because it:

- failed
- is being replaced
- is being upgraded
- is no longer required
- is being taken out of service

Now the cluster becomes:

```text
Cache A
Cache B
Cache C
```

The modulo calculation changes from:

```text
hash(key) % 4
```

to:

```text
hash(key) % 3
```

Again, many keys can receive different destinations.

So both operations can cause significant redistribution:

```text
Add Node
   |
   v
Mapping Changes

Remove Node
   |
   v
Mapping Changes
```

---

## 13. Why Recalculating Everything Is Expensive

One possible response is to accept the redistribution and move or rebuild everything.

For example:

```text
Add Cache D
     |
     v
Recalculate ownership
     |
     v
Process millions of keys
     |
     v
Move/rebuild cache entries
```

For a small system, this may be acceptable.

But consider a larger system:

```text
100 million keys
500 million keys
1 billion keys
```

A topology change should ideally not require unnecessarily processing the entire keyspace.

Large-scale redistribution can create:

- network traffic
- CPU usage
- database reads
- cache misses
- cache warm-up work
- latency spikes
- operational complexity

The goal is therefore not only to distribute keys.

The goal is to distribute them **without causing unnecessary movement when the cluster changes**.

---

## 14. What Do We Actually Want?

A better key-distribution strategy should ideally provide several properties.

### 14.1 Deterministic Routing

For a stable cluster:

```text
user:1001 -> Cache B
user:1002 -> Cache A
user:1003 -> Cache C
```

Repeated requests for the same key should consistently reach the same node.

---

### 14.2 Reasonable Distribution

We do not want all keys concentrated on one server.

For example, this is undesirable:

```text
Cache A -> 90% of keys
Cache B -> 5% of keys
Cache C -> 5% of keys
```

We want the keyspace to be reasonably distributed across the available nodes.

Perfectly equal distribution is not always possible, but severe imbalance should be avoided.

---

### 14.3 Minimal Key Movement

When a node is added:

```text
A
B
C
```

becomes:

```text
A
B
C
D
```

we ideally want:

```text
Most existing keys -> stay where they are
Some keys          -> move to D
```

rather than:

```text
Most existing keys -> move
```

This is one of the most important requirements.

---

### 14.4 Predictable Node Removal

If a node disappears:

```text
A
B
C
D
```

becomes:

```text
A
B
C
```

we need a predictable way to reassign the keys that belonged to D.

Again, the goal is to avoid unnecessarily disturbing unrelated keys.

---

### 14.5 Efficient Routing

The routing operation itself should be fast.

A distributed system may perform millions or billions of routing decisions, so the lookup mechanism should not become a bottleneck.

---

## 15. The Core System-Design Question

We can now state the actual problem:

> **We have a large number of keys and a changing number of nodes. How can we distribute those keys across nodes while minimizing unnecessary movement when nodes are added or removed?**

This is the problem Consistent Hashing addresses.

---

## 16. Why This Is a Distributed-Systems Problem

At first glance, this may look like a simple hashing problem.

But the real challenge is the changing topology.

We are not only asking:

```text
Which node owns this key?
```

We are asking:

```text
Which node owns this key?

And what happens when:

    + a node is added?
    + a node is removed?
    + a node fails?
```

That changes the problem from simple hashing into a distributed-systems design problem.

---

## 17. The Key Insight

The important requirement is:

> **A change in cluster size should affect only the keys that actually need to move.**

Conceptually:

```text
Cluster Changes
      |
      v
Ownership Changes
      |
      +----------------------+
      |                      |
      v                      v
Unrelated Keys          Affected Keys
Stay Stable             May Move
```

This is the direction Consistent Hashing takes.

We will not jump directly into the implementation yet.

First, we should understand the behavior of the naive modulo approach and measure how many keys actually move.

---

## 18. What We Will Measure

In the next section, we will create a simple experiment.

For example:

```text
Number of keys: 100,000

Initial nodes:
A
B
C
```

We will calculate the destination of every key.

Then we will add:

```text
D
```

and calculate the destination again.

Finally, we will compare the two mappings.

We will measure:

```text
Total keys
Keys that stayed
Keys that moved
Percentage of keys moved
```

Conceptually:

```text
100,000 keys
      |
      v
3 nodes
      |
      v
Record ownership
      |
      v
Add 4th node
      |
      v
Calculate ownership again
      |
      v
Compare
      |
      v
Measure redistribution
```

This gives us a concrete baseline before introducing Consistent Hashing.

---

## 19. Learning Path

This repository will build the concept step by step:

```text
Business Problem
      |
      v
Naive Modulo Hashing
      |
      v
Measure Key Redistribution
      |
      v
How Consistent Hashing Works
      |
      v
Basic Hash Ring
      |
      v
Node Addition and Removal
      |
      v
Virtual Nodes
      |
      v
Distribution and Rebalancing
      |
      v
Real-World Use Cases
      |
      v
Consistent Hashing vs Alternatives
      |
      v
Production Considerations
```

The next file is:

```text
docs/02_naive_modulo_hashing.md
```

There we will implement the simplest key-to-node mapping and understand its behavior before moving to the Consistent Hashing approach.
