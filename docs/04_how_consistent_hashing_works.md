# How Consistent Hashing Works

In the previous documents, we used naive modulo hashing to distribute keys across servers and measured how many assignments changed when the number of servers changed.

The basic modulo rule was:

```python
server_index = hash(key) % number_of_servers
```

This is simple, but changing the number of servers changes the mapping calculation for every key. As a result, a large portion of the keyspace can be assigned to different servers.

Consistent hashing addresses this problem by organizing servers and keys on a **logical hash ring**.

The goal is not to eliminate redistribution completely. The goal is to reduce how much of the keyspace needs to move when a server is added or removed.

This document explains the core idea before we implement it in Python.

---

## 1. The Problem We Want to Solve

Imagine a distributed cache with three servers:

```text
Server A
Server B
Server C
```

Our application has many keys:

```text
user:1001
user:1002
user:1003
product:2001
product:2002
session:abc
```

The application needs a predictable way to decide which server owns each key.

With modulo hashing, a key is assigned by calculating:

```python
hash(key) % number_of_servers
```

When we add a server, the number of servers changes. This can cause many existing keys to map to a different server.

In a cache, changed assignments may cause cache misses. In a storage system, they may require data movement or changes to routing metadata.

We want a mapping strategy that makes server membership changes less disruptive.

---

## 2. The Core Idea: A Logical Hash Ring

Consistent hashing maps both servers and keys into the same logical hash space.

Instead of using a server count as a modulo divisor, imagine the hash space arranged in a circle.

```text
                  0
             .-----------.
          .                 .
        .       Server A      .
       /                       \
      |                         |
      |                         |
      | Server C       Server B |
       \                       /
        .                   .
          .               .
             '-----------'
```

The circle is conceptual. We do not need to draw a physical circle or store coordinates in a graphical form. We use numeric hash values and sort them.

For example, imagine the hash space runs from:

```text
0 -------------------------- 999
```

The end connects back to the beginning, so the space behaves like a ring:

```text
... 998, 999, 0, 1, 2 ...
```

This wrap-around behavior is an important part of the algorithm.

---

## 3. Place Servers on the Ring

First, calculate a hash position for each server.

For illustration, suppose we get:

```text
Server A -> 120
Server B -> 430
Server C -> 780
```

These positions define the servers' locations on the ring.

```text
0 --------------------------------------------------- 999
       A(120)              B(430)              C(780)
```

The values above are illustrative. A real implementation uses a hash function to calculate positions from server identifiers.

The server identifier should be stable. For example:

```text
cache-server-01
cache-server-02
cache-server-03
```

If the same identifier is hashed with the same hash function, it should map to the same ring position.

---

## 4. Place Keys on the Same Ring

Next, hash each key into the same hash space.

Suppose the key positions are:

```text
user:1001 -> 200
user:1002 -> 500
user:1003 -> 900
```

Now the ring contains both server positions and key positions:

```text
0 --------------------------------------------------- 999
       A(120)  key(200)  B(430)  key(500)  C(780)  key(900)
```

The keys and servers are represented as positions in one shared logical space.

The next question is:

**How does a key choose its server?**

---

## 5. Find the First Server Clockwise

The standard basic rule is:

> Starting from a key's position, move clockwise around the ring until you encounter the first server.

That server owns the key.

Using our example:

```text
Server A -> 120
Server B -> 430
Server C -> 780

user:1001 -> 200
user:1002 -> 500
user:1003 -> 900
```

The assignments are:

```text
user:1001 at 200
    -> next server clockwise is B at 430

user:1002 at 500
    -> next server clockwise is C at 780

user:1003 at 900
    -> wrap around to A at 120
```

Therefore:

```text
user:1001 -> Server B
user:1002 -> Server C
user:1003 -> Server A
```

Notice the wrap-around case. If a key is positioned after the last server on the ring, it continues from the beginning.

This is why the hash space is a ring rather than a straight line.

---

## 6. Why Adding a Server Moves Fewer Keys

Suppose we add a fourth server:

```text
Server D -> 600
```

Before the addition, the servers were at:

```text
A(120), B(430), C(780)
```

After the addition:

```text
A(120), B(430), D(600), C(780)
```

Consider the clockwise ownership ranges:

```text
Before:

B owns keys after A(120) through B(430)
C owns keys after B(430) through C(780)
A owns keys after C(780) through wrap-around to A(120)
```

After adding D at position 600:

```text
B owns keys after A(120) through B(430)
D owns keys after B(430) through D(600)
C owns keys after D(600) through C(780)
A owns keys after C(780) through wrap-around to A(120)
```

Only keys in the range that now ends at D need to change ownership: keys that previously mapped to C but fall between B and D.

In the basic model, the other ranges remain owned by the same servers.

```text
Add Server D
      |
      v
Insert D at one ring position
      |
      v
One existing ownership range is split
      |
      v
Only keys in the affected range change owner
```

The exact number of keys depends on where D lands and how keys are distributed around the ring.

This is the central benefit of consistent hashing: a membership change affects a local portion of the ring rather than recalculating every key against a new server-count divisor.

---

## 7. Removing a Server

Now imagine Server B is removed.

In the basic ring model, the range that B owned is assigned to the next server clockwise, which is Server D if D exists after B.

Conceptually:

```text
Before removal:

A -> its ownership range
B -> its ownership range
D -> its ownership range
C -> its ownership range
```

After removing B:

```text
A -> its ownership range
D -> B's former range plus its existing range
C -> its ownership range
```

Only the removed server's ownership range needs a new owner in this simplified model.

In real systems, replicas, data recovery, capacity limits, and failure handling add more considerations. The ring explains the routing principle, not a complete storage migration protocol.

---

## 8. Compare the Two Approaches

| Concern | Naive modulo hashing | Consistent hashing |
|---|---|---|
| Basic assignment | `hash(key) % N` | First server clockwise from the key's ring position |
| Uses server count directly in every key calculation | Yes | No |
| Server added | Many assignments may change | A portion of the ring changes ownership |
| Server removed | Many assignments may change | The removed server's range is reassigned |
| Lookup | Simple modulo operation | Find the next server position on the ring |
| Implementation complexity | Very low | Higher; needs ring positions and lookup logic |
| Distribution balance | Depends on hash and key distribution | Depends on server positions and key distribution |

Consistent hashing introduces additional logic. It is useful when reducing redistribution matters enough to justify that complexity.

---

## 9. What Does “Consistent” Mean Here?

The name does not mean that every key stays on the same server forever.

Keys can move when:

- a server is added
- a server is removed
- server positions or identifiers change
- the ring configuration changes

The intended property is that a change in membership affects a limited portion of the mapping, rather than causing widespread remapping solely because the server count changed.

Consistent hashing is therefore about **limiting redistribution**, not preventing it.

---

## 10. The Basic Algorithm

A simple consistent-hashing implementation follows these steps.

### Build the ring

1. Choose a stable hash function.
2. Hash each server identifier to get a ring position.
3. Store the server positions in sorted order.

### Route a key

1. Hash the key to get its ring position.
2. Find the first server position that is greater than or equal to the key position.
3. If no server position is large enough, wrap around to the first server position.
4. Return that server.

In pseudocode:

```text
add_server(server):
    position = hash(server)
    insert position into sorted ring

get_server(key):
    key_position = hash(key)
    find first server position >= key_position

    if no such server exists:
        return server at first ring position

    return server at found position
```

This describes the basic version with one ring position per server. Later, we can extend it with virtual nodes to improve balance.

---

## 11. Why Use a Stable Hash Function?

All application instances must calculate the same ring positions.

If two application processes use different server positions, the same key may be routed to different servers depending on which process handles the request.

That can create inconsistent routing and cache misses.

For this reason, a distributed implementation should use a stable, consistently configured hash function rather than relying on Python's built-in `hash()` for strings.

The hash function and input encoding must be consistent across all participating processes.

---

## 12. A Ring Does Not Automatically Guarantee Perfect Balance

Consistent hashing reduces redistribution, but it does not guarantee that every server owns exactly the same number of keys.

Suppose server positions are unevenly spaced:

```text
A(100) ---- B(120) ------------------------ C(800)
```

The ownership ranges differ in size.

If keys are distributed uniformly across the hash space, a server with a larger range may receive more keys.

Also, equal key counts do not necessarily mean equal load. One key might be requested millions of times while another is rarely accessed.

So there are two separate concerns:

1. **Redistribution:** How many keys change owner when membership changes?
2. **Load balance:** How evenly are keys or requests distributed across servers?

A design can perform well on one measure and still need improvement on the other.

---

## 13. Virtual Nodes: An Improvement We Will Add Later

One ring position per server can produce uneven ownership ranges.

A common improvement is to assign multiple positions to each physical server. These positions are called **virtual nodes**, or **vnodes**.

Instead of placing a server once:

```text
Server A -> one position
```

we place several virtual positions:

```text
Server A -> A#1, A#2, A#3, A#4, ...
```

The ring now has more ownership boundaries, which generally improves distribution when positions are well spread.

Virtual nodes also make it possible to represent servers with different capacities by assigning them different numbers of virtual nodes, although this requires careful configuration and measurement.

We will treat virtual nodes as a separate implementation step so the basic ring algorithm remains easy to understand first.

---

## 14. Production Considerations

The ring is a routing model, not a complete distributed-system solution.

A production design still needs to consider:

- **Membership agreement:** all application instances need a consistent view of active servers.
- **Stable hashing:** all instances must calculate the same positions.
- **Failure handling:** a server can fail without being cleanly removed from configuration.
- **Data availability:** a key may not yet exist on its newly assigned owner.
- **Replication:** important data may need copies on multiple servers.
- **Capacity:** equal ring ownership does not guarantee equal CPU, memory, or request load.
- **Migration:** some systems need an explicit process to copy data before switching ownership.
- **Observability:** track request load, cache hit rate, key distribution, and movement during membership changes.

These concerns do not invalidate consistent hashing. They describe the additional work needed to use it reliably.

---

## 15. What We Have Learned

The core algorithm can be summarized as:

```text
Hash servers onto a ring
          |
          v
Hash each key onto the same ring
          |
          v
Find the first server clockwise
          |
          v
Route the key to that server
```

When a server is added or removed, only part of the ring's ownership changes in the basic model.

This gives us a way to reduce key redistribution compared with naive modulo hashing.

The next step is to turn this concept into a small runnable Python implementation, then measure its behavior against the modulo-hashing baseline.

---

## Key Takeaways

- Consistent hashing places server identifiers and keys in the same logical hash space.
- A key is assigned to the first server clockwise from its ring position.
- The ring wraps around from its final position to its first.
- Adding a server splits an existing ownership range; removing one causes its range to be reassigned.
- Consistent hashing limits redistribution but does not eliminate it.
- Basic consistent hashing can still have uneven ownership ranges.
- Virtual nodes are a common way to improve distribution.
- Production systems still need consistent membership, failure handling, data availability, and capacity planning.

## Next

In the next document, we will implement the basic hash ring in Python. We will keep the implementation small and runnable, using a stable hash function and sorted server positions before introducing virtual nodes.
