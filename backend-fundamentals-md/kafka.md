# Apache Kafka — Complete Structured Reference

> Reorganized from raw notes. Every concept now lives in exactly one place.
> Reading order: high-level architecture → core components → configuration → failure & scale.
>
> **Legend:** 📌 Definition · ⚙️ Config · 💡 Best practice · ⚠️ Pitfall · 🔄 Flow

---

## Table of Contents

| Part | Topic |
|------|-------|
| 0 | [Concept Map and Mental Model](#part-0-concept-map-and-mental-model) |
| 1 | [What Kafka Actually Is](#part-1-what-kafka-actually-is) |
| 2 | [Cluster and Brokers](#part-2-cluster-and-brokers) |
| 3 | [Topics and Partitions](#part-3-topics-and-partitions) |
| 4 | [Replication, Leadership and Durability](#part-4-replication-leadership-and-durability) |
| 5 | [Storage and Retention](#part-5-storage-and-retention) |
| 6 | [Producers](#part-6-producers) |
| 7 | [Consumers and Consumer Groups](#part-7-consumers-and-consumer-groups) |
| 8 | [Offsets and Delivery Semantics](#part-8-offsets-and-delivery-semantics) |
| 9 | [Control Plane, Controller and KRaft](#part-9-control-plane-controller-and-kraft) |
| 10 | [Failure Handling](#part-10-failure-handling) |
| 11 | [Performance, Why Kafka Is Fast](#part-11-performance-why-kafka-is-fast) |
| 12 | [Scaling and Operational Reality](#part-12-scaling-and-operational-reality) |

---

## Part 0: Concept Map and Mental Model

```
+===================================================================+
|                PART 0 - CONCEPT MAP & MENTAL MODEL                |
+===================================================================+
```

### 📌 The eight concepts you must connect

Everything in Kafka is one of these eight things, or a relationship between them:

```
  1. Cluster
  2. Brokers
  3. Topics
  4. Partitions
  5. Replication
  6. Producers
  7. Consumers / Consumer Groups
  8. Controller / KRaft
```

Then layer these on top:

```
  Offsets                     Rebalancing
  Log / storage               Exactly-once / idempotence
  Leader/follower replication Performance & scaling
  ISR                         End-to-end message journey
  Acknowledgements
  Failure handling
```

### 💡 The architecture you should memorize

Don't memorize 50 disconnected Kafka facts. Memorize this one tree — every fact
in this document hangs off a node in it:

```
                         KAFKA CLUSTER
                              |
                   +----------+----------+
                   |                     |
              KRaft Controllers       Brokers
              (control plane)       (data plane)
                                         |
                                      Topics
                                         |
                                    Partitions
                                         |
                              +----------+----------+
                              |                     |
                           Leader               Followers
                              |                     |
                              +---- replication ----+
                                         |
                                      Storage
                                         |
                                      Offsets
                                         |
                                  Consumer Groups
                                         |
                                     Consumers
```

### 🔄 The end-to-end message journey

```
              APPLICATION
                  |
                  v
              PRODUCER
                  |
                  |  key
                  v
             PARTITIONER
                  |
                  v
              PARTITION
                  |
                  v
           LEADER BROKER
                  |
                  +--------> FOLLOWER
                  +--------> FOLLOWER
                  |
                  v
                 ACK
                  |
                  v
            CONSUMER GROUP
                  |
                  v
               CONSUMER
                  |
                  v
               PROCESS
                  |
                  v
           COMMIT OFFSET
```

### 📌 The most important distinction: Control Plane vs Data Plane

This is the single most useful architecture-level mental model, and it makes
Kafka architecture questions dramatically easier to answer.

```
       CONTROL PLANE                          DATA PLANE
  ------------------------              ------------------------
     KRaft Controllers                        Producer
            |                                     |
            v                                     v
      cluster metadata                          Broker
            |                                     |
            v                                     v
    partition assignments                      Partition
            |                                     |
            v                                     v
      leader elections                        Replication
            |                                     |
            v                                     v
     broker membership                          Consumer
```

### Kafka's architecture in one picture

```
                         +-----------------------+
                         |    KRaft Controllers  |
                         |   Cluster Metadata    |
                         +-----------+-----------+
                                     |
                         cluster coordination
                                     |
          +--------------------------+-------------------------+
          |                          |                         |
          v                          v                         v
     +---------+               +---------+               +---------+
     | Broker 1|               | Broker 2|               | Broker 3|
     +----+----+               +----+----+               +----+----+
          |                         |                         |
          |                         |                         |
          +-------------------------+-------------------------+
                                    |
                                  Topics
                                    |
                         +----------+----------+
                         |                     |
                       orders              payments
                         |
                  +------+------+
                  |      |      |
                 P0     P1     P2
                  |      |      |
             replication/leader
                  |      |      |
                  v      v      v

             +----------------------+
             |    Consumer Group    |
             |                      |
             | C1       C2       C3 |
             +----------------------+
```

---

## Part 1: What Kafka Actually Is

```
+===================================================================+
|                  PART 1 - WHAT KAFKA ACTUALLY IS                  |
+===================================================================+
```

### 📌 Message queue or event stream?

Kafka is fundamentally an **Event Streaming Platform**.

But it *can* behave like a message queue, depending on the consumption pattern
you choose. The platform doesn't force one model on you.

The reason it can do both: **each consumer reads from its own independent pointer.**

It is entirely possible — and normal — that the payment service has processed
every message while the email service is still 10 messages behind. Neither one
blocks or affects the other.

### 📌 Why Kafka is not simply a queue

A traditional queue destroys data as it is consumed:

```
       TRADITIONAL QUEUE                        KAFKA
     ---------------------              ---------------------
           Producer                          Producer
              |                                  |
              v                                  v
            Queue                          Partition log
              |                              |         |
              v                              v         v
           Consumer                  Consumer      Consumer
              |                       Group A       Group B
              v                          |             |
       message removed                   v             v
                                      offset       different
                                                    offset
```

The same log. Two groups. Two completely independent read positions.

---

## Part 2: Cluster and Brokers

```
+===================================================================+
|                    PART 2 - CLUSTER & BROKERS                     |
+===================================================================+
```

### 📌 What a broker is

A **broker** is a Kafka server that stores data and serves read/write requests.

Think of a broker as:

```
  - a machine
  - running Kafka
  - storing partitions on disk
```

### 📌 What a Kafka cluster is

A **Kafka cluster** is a group of Kafka brokers working together as one Kafka system.
Kafka runs as a cluster of many servers 

```
+-----------------------------------------------------------------------------------+
|                            KAFKA CLUSTER - SERVERS                                |
+---------------------------+---------------------------+---------------------------+
|         BROKER 1          |         BROKER 2          |         BROKER 3          |
|                           |                           |                           |
|       +-----------+       |       +-----------+       |       +-----------+       |
|       |  [=  =]   |       |       |  [=  =]   |       |       |  [=  =]   |       |
|       |  [=  =]   |       |       |  [=  =]   |       |       |  [=  =]   |       |
|       +-----------+       |       +-----------+       |       +-----------+       |
|                           |                           |                           |
+---------------------------+---------------------------+---------------------------+
```

One Kafka installation with multiple brokers = a cluster.
**Kafka scales by adding brokers.**

Example — topic `orders` with 6 partitions spread across 3 brokers:

```
  Topic:      orders
  Partitions: 6

  Broker 1  ->  P0, P3
  Broker 2  ->  P1, P4
  Broker 3  ->  P2, P5
```

### ⚙️ Avoiding single points of failure

To avoid single points of failure, partitions are replicated internally across
brokers, controlled by `replication_factor`. See
[Part 4](#part-4-replication-leadership-and-durability) for the full mechanism.

### 🔄 The broker's role in the data plane

```
  Producer --(Publishes)--> [   BROKER   ] --(Fetches)--> Consumer 1 --> Application
                            [  Topic P2  ]
                            [ Log: 100.. ]
                            [ Offset:103 ]
```

The broker is responsible for four things:

**1. Storage & persistence** — stores records 100, 101 and 102 sequentially on
disk inside partition P2.

**2. Offset tracking** — receives and saves the consumer group's committed offset.

**3. Fetch handling** — serves records to Consumer 1 when requested, and updates
what has been delivered.

**4. Failover coordination** — when Consumer 1 crashes, the **group
coordinator** detects the failure via missed heartbeats, rebalances the group,
and the new consumer resumes fetching from the committed offset. The group
coordinator is one specific broker elected to manage that particular consumer
group — not "any broker", and **not** the KRaft controller, which handles
*broker* failure rather than *consumer* failure. See
[Part 10](#part-10-failure-handling).

Notice what the broker does **not** do — this is the source of much of its speed.
It never deserializes your messages, applies business logic, or filters per
consumer. See [Part 11](#part-11-performance-why-kafka-is-fast).

---

## Part 3: Topics and Partitions

```
+===================================================================+
|                   PART 3 - TOPICS & PARTITIONS                    |
+===================================================================+
```

### 📌 A topic is logical, not physical

A **topic** is a logical stream/category of messages — for example, `orders`.

But a topic itself is **not** where Kafka physically stores anything.

So where are events actually stored? **Inside brokers, in partitions.**

Since Kafka as a system contains multiple brokers, data lives inside those
brokers — specifically in partitions. Inside the broker, partitions are what
actually hold the events. A single broker can hold data from many different topics.

💡 **The analogy that makes this stick:**

```
  Topic       ->  folder name
  Partitions  ->  the actual files inside it

  You cannot write data into the folder.
  You write data into the files.
```

### 📌 What a partition is

A **partition is an ordered, append-only log.**

Kafka performs hashing on the message key, then assigns the event to a specific
partition.

> ⚠️ **The ordering rule — memorize this exactly:**
> Ordering is maintained **within a partition**, but **never across partitions.**

A partition physically looks like this:

```
  orders-P0

  Offset     Message
  ------     -------
  0          Order A
  1          Order B
  2          Order C
  3          Order D
  4          Order E
```

A topic is not physical storage — it is a logical grouping. Kafka needs physical
storage, and that is exactly what partitions are.

### 📌 Why partitions exist

Because **one partition has limited throughput.**

Instead of funnelling everything through one server:

```
        WITHOUT PARTITIONS                    WITH PARTITIONS

              Topic                                orders
                |                              /     |     \
                v                            P0     P1     P2
            One server                       |      |      |
                                          Broker1 Broker2 Broker3
         (throughput ceiling)
                                       (producers and consumers
                                         work in parallel)
```

Kafka's design goal was **massive throughput + horizontal scaling**. That is
impossible without partitions.

### 📌 What partitions actually solve

**1. Scalability** — each partition is an independent log and can live on a
different broker. So Kafka scales like this:

```
  more partitions  ->  more parallelism  ->  more throughput
```

**2. Parallel consumers** — if a topic has 5 partitions, up to 5 consumers can
read in parallel *per consumer group*. Without partitions, only one consumer
would ever be useful.

### 📌 Anatomy of a Kafka message (record)

Before going further: this is the atomic unit everything else moves around. A
record is not just a payload — it carries its own routing and ordering
information.

```
+-----------------------------------------------------------------+
|                     Kafka Message (Record)                      |
+-----------------------------------------------------------------+
| Topic: "orders"                                                 |
| Partition: (Decided by Key or Round-robin)                      |
| Key: "order-12345" (Ensures Ordering per Key)                   |
| Value: {                                                        |
|   "order_id": "12345",                                          |
|   "customer": "John Doe",                                       |
|   "amount": 250.75,                                             |
|   "status": "pending"                                           |
| }                                                               |
| Headers: { "source": "web-app", "timestamp": "1700000000000" }  |
| Timestamp: "1700000000000"                                      |
+-----------------------------------------------------------------+
```

⚙️ Field by field:

- **Topic** — the logical stream it belongs to.
- **Partition** — *not* set by you directly. Decided by the key, or by the
  sticky partitioner when there is no key (see below).
- **Key** — optional, but it is what **ensures ordering per key**, because it
  pins every record with that key to one partition.
- **Value** — the actual payload. The broker never deserializes this.
- **Headers** — arbitrary metadata key/value pairs, useful for tracing and
  routing without touching the payload.
- **Timestamp** — attached to the record.

💡 The `Key` field is the single most consequential choice in the whole record.
It decides partition, and therefore decides ordering. Everything in the next two
sections follows from it.

### 📌 Partition key — how a message picks its partition

For the default Kafka producer partitioner, Kafka uses a **murmur2** hash for
keyed messages.

Conceptually:

```
  key       = "order_123"
  hash      = murmur2(key)
  partition = toPositive(hash) % numberOfPartitions
```

`hash % partition_count` is the conceptual default behaviour for keyed
partitioning, with Kafka's default partitioner using Murmur2. The actual code
lives in the Kafka client library's producer partitioner implementation.

So with 3 partitions:

```
  murmur2("order_123")
          |
          v
    some integer
          |
          v
  positive integer % 3
          |
          v
      0  /  1  /  2
```

### 📌 Sticky partitioner — how *unkeyed* messages pick a partition

The murmur2 rule above applies to records **that have a key**. But what about
records sent without one?

A **sticky partitioner** is a record batching strategy used by Kafka producers to
improve performance when sending messages **without explicit keys**. It was
created to solve a critical flaw in Kafka's original producer design: **poor
batching when messages didn't have keys.**

### ⚠️ The problem it solves — round-robin inefficiency

Prior to **Kafka 2.4**, when a producer sent records without keys it used a basic
**round-robin** approach: Record 1 to Partition 0, Record 2 to Partition 1,
Record 3 to Partition 2, and so on.

Because messages were split across multiple partitions one by one, batch buffers
filled up **slowly**. The producer had to send many tiny network requests,
causing higher latency and increased CPU overhead.

```
  ROUND-ROBIN (pre-2.4)
  ---------------------
  Batch Partition 0: [Record 1]  --> sent immediately (small payload)
  Batch Partition 1: [Record 2]  --> sent immediately (small payload)
  Batch Partition 2: [Record 3]  --> sent immediately (small payload)
```

The context that makes this matter: to achieve ultra-high throughput, a Kafka
producer does **not** send every message to the broker individually. It holds
messages in **memory buffers** and waits to group them into a single batch before
making a network request. Round-robin actively sabotaged that.

### 🔄 How the sticky partitioner works

It "sticks" to one partition until that batch is full, *then* moves on:

```
  STICKY PARTITIONING (default since 2.4)
  ---------------------------------------
  Partition 0: [Record 1, Record 2, Record 3, Record 4]
                        |
                        v
               sent as ONE dense batch

  (the next batch "sticks" to Partition 1, then Partition 2, etc.)
```

Same total number of records. Far fewer network requests. Records still end up
evenly spread across partitions — just in dense batches rather than a trickle.

### ⚙️ When is a batch actually sent?

A batch is triggered and sent to the broker when **either** of these limits is
met **first**:

```
+----------------+----------------------------------------------+------------------+
| Key            | Trigger                                      | Typical value    |
+================+==============================================+==================+
| batch.size     | Memory limit for one partition's batch       | 16 KB            |
| linger.ms      | Max time a message may wait in the buffer    | 10 ms            |
+----------------+----------------------------------------------+------------------+
```

💡 These two knobs are the throughput/latency dial. Raising `linger.ms` lets
batches grow denser (more throughput, more latency); lowering it ships sooner
(less latency, more requests). See also
[Part 11](#part-11-performance-why-kafka-is-fast), where batching is one of the
five reasons Kafka is fast.

### ⚠️ What happens if you increase partitions

This is the classic trap. Suppose:

```
  3 partitions
  hash(order_123) = 100
  100 % 3 = 1        ->  order_123 lands on P1
```

Now you grow the topic to 4 partitions:

```
  4 partitions
  hash(order_123) = 100
  100 % 4 = 0        ->  order_123 lands on P0
```

**Same key. Different partition.** And here is why that hurts:

```
   BEFORE the resize                    AFTER the resize
   ------------------                   -----------------
   P1:  CREATED                         P1:  CREATED     <- history stranded here
        PAID                                 PAID
        SHIPPED                              SHIPPED

                                        P0:  DELIVERED   <- new events land here
```

The order's earlier events stay behind in P1 forever, while every *new* event
for that same key now routes to P0. Since ordering is only guaranteed *within*
a partition, the lifecycle of `order_123` is now split across two logs with **no
ordering guarantee between them.** A consumer can legitimately see `DELIVERED`
before `SHIPPED`.

Nothing is rewritten or migrated when you resize. Existing records stay exactly
where they were written; only the **routing of new records** changes.

So, to summarize the resize rule:

```
  3 partitions -> 6 partitions        [OK]  structurally possible
                                      [!!]  breaks per-key ordering across the change
```

Kafka partitions can be scaled horizontally by increasing the partition count,
but increasing partitions changes key-to-partition mapping and therefore affects
ordering guarantees for keyed messages.

---

## Part 4: Replication, Leadership and Durability

```
+===================================================================+
|           PART 4 - REPLICATION, LEADERSHIP & DURABILITY           |
+===================================================================+
```

### 📌 The two units, kept straight

```
  Partition  =  logical unit of data
  Broker     =  machine/server that stores partitions
```

### 📌 Leader and followers

For every partition, **one replica is the leader. The others are followers.**

- Producers normally send writes to the **leader**.
- Consumers fetch from the **leader** by default in the common setup.
- The followers **replicate the leader's log**.

### 📌 Why only one leader?

Suppose two brokers could independently accept writes for the same partition:

```
  Broker 1              Broker 2
  P0:                   P0:
    0  A                  0  A
    1  B                  1  X       <-- conflict
```

Now you have two conflicting histories for the same partition and no way to
reconcile them. A single leader per partition is what makes the log a single,
totally-ordered truth.

### Replica placement examples

**3 partitions across 2 brokers** *(leaders shown; replicas omitted for clarity)*:

```
                Broker 1        Broker 2
                --------        --------
  P0             Leader
  P1                             Leader
  P2             Leader
```

**Replication factor = 3, across 3 brokers:**

```
                Broker 1     Broker 2     Broker 3
                --------     --------     --------
  P0             Leader       Replica      Replica
  P1             Replica      Leader       Replica
  P2             Replica      Replica      Leader
```

In *this* replication-factor-3 example, each partition therefore has three
copies. The number of copies is always whatever `replication_factor` is set to —
nothing about Kafka forces it to 3.

⚙️ The **KRaft controller** assigns partition replicas to brokers and manages
partition leadership. See [Part 9](#part-9-control-plane-controller-and-kraft).

### 🔄 What replication buys you

If Broker 1 dies:

```
  P0
   |
  Broker 1  [DEAD]

  Kafka promotes a surviving replica:

  Broker 2  ->  new Leader
  Broker 3  ->  Replica
```

### 📌 ISR — In-Sync Replicas

The **ISR** is the set of replicas currently caught up with the leader.

```
  Start:   ISR = { Broker 1, Broker 2, Broker 3 }

  Broker 3 becomes slow:

    Broker 1  ->  Leader     [OK]
    Broker 2  ->  Replica    [OK]
    Broker 3  ->  Replica    [SLOW]

  Kafka removes Broker 3 from the ISR:

  Now:     ISR = { Broker 1, Broker 2 }
```

💡 **Why the ISR matters:** if the leader dies, Kafka selects the new leader from
the **in-sync** replicas. A replica that has fallen out of the ISR is not an
eligible candidate — which is precisely what prevents a stale replica from being
promoted and silently losing committed records.

### ⚙️ `acks` — how much confirmation the producer demands

The producer sends `OrderCreated` to the leader. How much confirmation does it
wait for before considering the write successful? That is controlled by `acks`.

```
+-----------+----------------------------------------+------------------+------------------+
| acks      | Producer waits for                     | Speed            | Durability       |
+===========+========================================+==================+==================+
| 0         | Nothing. Fire and forget.              | Fastest          | Weakest          |
| 1         | Leader's local write only              | Middle           | Middle           |
| all       | Leader + required ISR replicas         | Slowest          | Strongest        |
+-----------+----------------------------------------+------------------+------------------+
```

**`acks=0`** — the producer doesn't wait for acknowledgement at all.

```
  Producer
     |
     +--> Broker
          "hopefully received"
```

Fastest, weakest durability guarantee.

**`acks=1`** — the leader acknowledges after writing locally.

```
  Producer
     |
     v
   Leader
     |
   write
     |
     v
    ACK
```

Followers might not have replicated yet — so a leader crash right here loses the
record.

**`acks=all`** — the leader waits until the required in-sync replicas have
acknowledged, according to Kafka's replication settings.

```
  Producer
     |
     v
   Leader
     +-----> Replica 1
     +-----> Replica 2
               |
               v
              ACK
```

This provides the strongest durability.

---

## Part 5: Storage and Retention

```
+===================================================================+
|                   PART 5 - STORAGE & RETENTION                    |
+===================================================================+
```

### 📌 Retention — Kafka does not delete on read

Kafka doesn't delete a record after consumption. It retains data based on
policies.

```
+--------------------+----------------------------------------------------------+
| Key                | Meaning                                                  |
+====================+==========================================================+
| retention.ms       | Delete segments older than this age                      |
| retention.bytes    | Delete oldest segments once the partition exceeds this   |
+--------------------+----------------------------------------------------------+
```

So the lifecycle of data looks like:

```
  Day 1:   events exist
  Day 2:   events exist
   ...
  Day N:   retention policy deletes old segments
```

💡 This is what lets consumers **replay historical events** — but only while
those events remain within the retention window. Retention is the boundary of
your replay ability.

### 📌 Log segments

Kafka doesn't keep an entire partition as one giant file. Partitions are divided
into **log segments**.

```
  P0
   |
   +-- segment-0001     offsets     0 -  999
   +-- segment-0002     offsets  1000 - 1999
   +-- segment-0003     offsets  2000 - 2999
```

Because the log is chunked this way, Kafka can **roll and delete old segments**
by simply dropping whole files — no scanning, no per-record bookkeeping. This is
one of the main reasons Kafka can handle very large volumes of data cheaply.

---

## Part 6: Producers

```
+===================================================================+
|                        PART 6 - PRODUCERS                         |
+===================================================================+
```

### 📌 Two separate decisions (frequently tested in interviews)

People collapse these into one. They are not the same decision, and they are not
made by the same component.

**Decision 1 — Which partition?** Made by the **producer's partitioner**:

```
  order_id
     |
     v
  partitioner    <--- Running in YOUR APP process (Client Library)
     |
     v
     P2          <--- Result computed locally in memory (e.g. murmur2("order_123") % 3 = 2)
```

```
hash_value = mmh264.hash32(key) & 0x7FFFFFFF
target_partition = hash_value % total_partitions

producer.produce(
    topic='orders',
    key=order_id,
    value='{"item": "Laptop", "price": 1200}',
    partition=target_partition  # Explicitly targeting the partition decided above
)
```

**Decision 2 — Which broker stores P2?** Determined by the **cluster/controller**:

```
     P2
     |
     v
  Leader  -> Broker 3
  Replica -> Broker 1
  Replica -> Broker 2
```

Put together:

```
  Producer
     |
     |  chooses partition
     v
    P2
     |
     |  controller determines replica placement
     v
  Broker 3 = Leader
  Broker 1 = Replica
  Broker 2 = Replica
```

💡 **The producer picks the partition. The controller picks the brokers.**

⚙️ *How* the partitioner decides depends on whether the record has a key:
**murmur2 hashing** if it does, the **sticky partitioner** if it doesn't. Both
are covered in [Part 3](#part-3-topics-and-partitions).

### 📌 Metadata — how the producer finds the leader

Before it can send anything, the producer needs to know:

```
  Where is topic orders?
  Where is P2?
  Who is the leader for P2?
```

So the producer requests Kafka **metadata**, and gets back the partition-to-leader
map:

```
  orders-P0  ->  Broker 1
  orders-P1  ->  Broker 3
  orders-P2  ->  Broker 2
```

Then it can send records **directly to the correct broker** — no proxying, no
routing layer:

### 🔄 Complete producer flow


What happens architecturally:

```
  Application
       |
       v
    Producer
       |
       |  key = ORD-123
       v
  Partitioner
       |
       |  hash(key)
       v
  Partition P2
       |
       |  metadata request
       v
    Kafka cluster
        |
        |  P2 leader = Broker 2
        v
  Broker 2
       |
       |  P2 Leader
       +-------------> Broker 1
       |                 P2 Replica
       |
       +-------------> Broker 3
                         P2 Replica
```

### 🔄 What happens when a producer sends a message

This is the full interview-quality answer, in nine steps:

```
  1. Application creates record
          |
  2. Producer assigns key
          |
  3. Partitioner selects partition
          |
  4. Producer uses metadata to find partition leader
          |
  5. Record sent to leader broker
          |
  6. Leader appends record to partition log
          |
  7. Followers replicate the record
          |
  8. Required acknowledgements received      (see acks, Part 4)
          |
  9. Producer receives ACK
```

---

## Part 7: Consumers and Consumer Groups

```
+===================================================================+
|               PART 7 - CONSUMERS & CONSUMER GROUPS                |
+===================================================================+
```

### 📌 The consumer group rule

> **Inside Kafka, a consumer cannot exist without a consumer group.**

Consumers can read from multiple partitions. But **within a single consumer
group, only one consumer can read from a given partition.**

```
  Partition P

  Consumer group 1 (c1, c2)  ->  only c1 can read from P
  Consumer group 2 (c3, c4)  ->  only c3 can read from P
```

Multiple consumers **can** read the same partition simultaneously — provided they
belong to **different** consumer groups. Within one group, a partition is
assigned to at most one consumer.

Worked example — group CG1 with consumers `c1, c2`, topic with partitions
`p1, p2, p3`:

```
  CORRECT                          WRONG
  -------                          -----
  c1 -> p1, p2                     c1 -> p1, p2
  c2 -> p3                         c2 -> p2, p3
                                          ^^
                                   p2 assigned to BOTH c1 and c2
                                   in the same group
```

### 📌 Consumer lag

**Consumer lag** is what you get when producers are producing at a much higher
rate than consumers are consuming. It is the distance between the latest offset
in the partition and the consumer group's committed offset.

### 📌 How do consumers know an event has arrived?

```
  [X]  Kafka does NOT push events to consumers.
  [OK] Consumers POLL. Kafka is pull-based.
```

**Key point: the consumer is never notified.** Instead:

```
  Consumer polls periodically
        |
        +--> no data?      broker HOLDS the request open (long poll)
        |
        +--> data arrives?  broker responds immediately
```

This is called **long polling**. It gives you push-like latency while keeping the
pull model's back-pressure properties — the consumer never receives more than it
asked for.

### 🔄 Complete consumer flow

```
  P2
   |
   v
  Consumer Group
   |
   v
  Consumer 1
   |
   v
  application processing
```

The consumer fetches records from P2:

```
  100  ->  ORD-123 CREATED
  101  ->  ORD-123 PAID
  102  ->  ORD-123 SHIPPED
```

The consumer processes them in order, then commits its offset:

```
  processed:          100, 101, 102
  committed offset:   103          <-- next offset to read, not the last one processed
```

💡 **Read that committed value carefully — it is the most commonly-confused
point in Kafka.** Kafka commits **`lastProcessedOffset + 1`**, the *next* offset
to read, not the last one processed. Having processed 100, 101 and 102, the
value actually stored is **103**. This is why `commitSync()` after processing
record 102 writes 103, and why a consumer that resumes reads 103 next.

If the consumer crashes after processing 102, another consumer picks up the
partition and resumes from the committed offset. **This is exactly where delivery
semantics become important** — see [Part 8](#part-8-offsets-and-delivery-semantics).

### 🔄 What happens when a consumer reads

```
  1. Consumer joins consumer group
          |
  2. Group coordinator assigns partitions
          |
  3. Consumer fetches records from partition leader
          |
  4. Application processes records
          |
  5. Consumer commits offset
```

### 📌 Consumer rebalancing

When group membership changes, Kafka must redistribute partitions.

```
  BEFORE               C2 crashes            AFTER (rebalance)
  ------               ----------            -----------------
  P0 -> C1                 [X]               P0 -> C1
  P1 -> C2              C2 is gone           P1 -> C3
  P2 -> C3                                   P2 -> C3
```

The surviving consumers absorb the orphaned partitions, and the new owner
continues from the **group's committed offsets** — not from the beginning, and
not from wherever the dead consumer happened to be in memory.

---

## Part 8: Offsets and Delivery Semantics

```
+===================================================================+
|               PART 8 - OFFSETS & DELIVERY SEMANTICS               |
+===================================================================+
```

### 📌 What an offset is, and who assigns it

**Does every event have an offset?** Yes — every event has one.

**What is its scope?** An offset is unique only **within a partition.**

**Who assigns it?** The **Kafka broker** — specifically the leader of that
partition.

**How?**

```
  1. Producer sends a batch to the partition leader
  2. Broker appends the records to the log
  3. Broker assigns offsets sequentially
```

Example — topic `Orders`, partition P0, leader Broker 1:

```
  Offset | Event
  -------+---------------------------
  0      | OrderCreated(101)
  1      | OrderCreated(102)
  2      | OrderCancelled(101)
```

> 📌 **Producers do NOT control offsets. Offsets are purely a broker
> responsibility.**

### ⚠️ There is no global Kafka offset

The offset is partition-specific. Full stop.

```
  CORRECT                          THERE IS NO SUCH THING AS
  -------                          -------------------------
  P0  ->  offset 100               "the Kafka offset"
  P1  ->  offset 57                "the topic offset"
  P2  ->  offset 891
```

Offsets are maintained **per consumer group, per partition.**

### 📌 `__consumer_offsets`

Committed offsets are stored in Kafka itself, in an internal topic called
`__consumer_offsets`. Each record in it is:

```
  (groupId, topic, partition)  ->  committedOffset
```

Think of it as a map:

```
+-------------------+----------+-----------+-------------------+
| groupId           | topic    | partition | committedOffset   |
+===================+==========+===========+===================+
| payment-service   | orders   | 0         | 125               |
| payment-service   | orders   | 1         | 88                |
+-------------------+----------+-----------+-------------------+
```

Written out longhand, the first row reads: group `payment-service`, topic
`orders`, partition 0, committed offset 125.

### ⚙️ Offset commit strategies

```
+----------------------+----------------------------------+------------------------------+
| Strategy             | Behaviour                        | Risk                         |
+======================+==================================+==============================+
| Auto commit          | Kafka commits on a timer         | Skips unprocessed records    |
| Manual sync          | Blocks until broker confirms     | Slower, but deterministic    |
| Manual async         | Fire and forget the commit       | Commit itself may be lost    |
+----------------------+----------------------------------+------------------------------+
```

**1. Auto commit** — Kafka commits periodically on a timer. Easy, but risky: the
timer can fire and commit offsets for records the consumer has **fetched but not
yet finished processing**. If the consumer then crashes, those records are never
reprocessed, because the committed offset has already moved past them. The loss
window comes from the *gap between fetch and process*, not from the commit
itself.

**2. Manual commit (recommended)** — commit only after successful processing.
Comes in two forms: **synchronous** and **asynchronous**.

💡 **Best practice — the order is the whole point:**

```
  process message
        |
        v
  commit offset
```

### 📌 Delivery guarantees

```
+-------------------+----------------------------------------+-------------------------------+
| Guarantee         | How you get it                         | Failure mode                  |
+===================+========================================+===============================+
| At-most-once      | Commit BEFORE processing               | Crash mid-process = data lost |
| At-least-once     | Commit AFTER processing                | Crash pre-commit = duplicates |
| Exactly-once      | Transactions + idempotent producer     | Complexity + throughput cost  |
+-------------------+----------------------------------------+-------------------------------+
```

⚙️ **At-least-once is not Kafka's out-of-the-box behaviour.** At-least-once *is*
commit-after-processing, but that is not what you get by default. Kafka's shipped
default is `enable.auto.commit=true` with `auto.commit.interval.ms=5000` — a
5-second timer that commits independently of whether processing finished, which
is exactly the auto-commit hazard described above. You get true at-least-once by
**turning auto-commit off** and committing manually after processing.

Walked through concretely, with the broker holding committed offset 100 and
records 100–102 fetched:

**At-least-once (most common).** The consumer reads 100–102, completes
application processing, *then* commits. If it crashes after processing but
before committing, the broker still holds 100. The replacement consumer fetches
100–102 again — **duplicate processing.**

**At-most-once.** The consumer fetches 100–102, immediately commits, *then*
processes. If it crashes mid-processing, the broker already saved the advanced
offset, so the replacement consumer resumes at 103 — **the unprocessed records
are missed permanently.**

**Exactly-once.** The broker works with producers and consumers via
**transactional APIs** to write records and commit offsets together, atomically.

💡 The delivery semantic you get depends entirely on **when the consumer tells
the broker to update the committed offset, relative to processing.** It is a
sequencing decision in your code, not a Kafka setting you flip.

---

## Part 9: Control Plane, Controller and KRaft

```
+===================================================================+
|            PART 9 - CONTROL PLANE: CONTROLLER & KRAFT             |
+===================================================================+
```

### 📌 Why a controller has to exist

Kafka needs *someone* to coordinate:

```
  - partition leadership
  - replica assignments
  - broker failures
  - leader elections
  - metadata
```

That someone is the **Kafka controller**.

Concretely — imagine topic `orders`:

```
  P0 -> Broker 1
  P1 -> Broker 2
  P2 -> Broker 3
```

Broker 2 crashes. Kafka must answer one question: **who is the new leader of P1?**

```
  After Broker 2 dies:
    P1:  Broker 3  ->  New Leader
```

But *who makes that decision?* The controller. Individual brokers cannot decide
this among themselves without risking split-brain.

### 📌 KRaft

**Modern Kafka uses KRaft for cluster metadata management. Older Kafka versions
used ZooKeeper.**

```
        OLD                          MODERN
       -----                        --------
       Kafka                         Kafka
         |                             |
         v                             v
     ZooKeeper              KRaft controller quorum
```

**"What is KRaft in Kafka?"** — KRaft is Kafka's built-in consensus mechanism for
managing cluster metadata. Kafka maintains a **controller quorum** using the
**Raft** protocol, with one active controller and replicated metadata logs. The
controller manages things like broker membership and partition leadership, and
when a controller fails, another controller can be elected from the quorum.

**"What is the metadata log?"** — It's an ordered, replicated log containing
Kafka cluster metadata changes, allowing controllers to maintain a consistent
view of cluster state.

### 📌 What KRaft actually stores

KRaft maintains a **metadata log**. Think of it as an event log of the cluster's
own shape:

```
  Metadata Log

  offset 0  ->  create topic orders
  offset 1  ->  create partition P0
  offset 2  ->  P0 leader = Broker 1
  offset 3  ->  P1 leader = Broker 2
  offset 4  ->  Broker 2 removed
  offset 5  ->  P1 leader = Broker 3
  ...
```

💡 Note the elegance: Kafka stores its **own cluster metadata as a replicated
log** — the same primitive it sells to you.

The metadata log contains:

```
  - Topic exists
  - Partition exists
  - Partition replicas
  - Partition leader
  - Broker registration
  - Configuration changes
  - ISR-related metadata / state changes
```

For example, this is exactly the kind of state that must be coordinated
consistently:

```
  Topic orders, Partitions = 3

  P0 leader = Broker 1
  P1 leader = Broker 2
  P2 leader = Broker 3
```

### 📌 The controller quorum

You run several controllers. One becomes the **ACTIVE CONTROLLER**; the rest are
followers.

```
              Controller 1
              +-----------+
              |  LEADER   |
              +-----+-----+
                    |
          +---------+---------+
          v                   v
 Controller 2            Controller 3
   follower                follower
```

This is a **Raft quorum**.

The whole control plane, in one picture:

```
                    KRaft Controller Quorum
                 +---------------------------+
                 |                           |
                 | C1       C2       C3      |
                 | |        |        |       |
                 | +--------+--------+       |
                 |          |                |
                 |     Metadata Log          |
                 |          |                |
                 +----------+----------------+
                            |
                     Cluster Metadata
                            |
             +--------------+--------------+
             |              |              |
             v              v              v
          Broker 1       Broker 2       Broker 3
             |              |              |
          P0 Leader      P1 Leader      P2 Leader
             |              |              |
          replicas       replicas       replicas
```

### 🔄 How a metadata change actually propagates

Suppose `C1 = leader`, `C2` and `C3` are followers, and C1 receives a
metadata-changing event: **Broker 2 crashed.**

The controller determines that P1's leader must change, and records that change
into the metadata log:

```
  Broker failure
        |
        v
  Controller leader
        |
        v
  Metadata log
        |
        v
  Replicated to controller quorum
        |
        v
  New cluster state
```

Now the whole cluster knows: **P1 -> Broker 3 is leader.**

### 📌 How does the controller know Broker 2 died?

The broker maintains ongoing communication with the controller:

```
  Broker 1  ----- heartbeat ----->  Controller
  Broker 2  ----- heartbeat ----->  Controller
  Broker 3  ----- heartbeat ----->  Controller
```

If Broker 2 stops communicating, the controller determines that the broker is
unavailable, and can then perform metadata and leadership changes.

> ⚠️ **Do not describe this in an interview as "the broker tells Kafka that it
> died."** Obviously it can't reliably do that — it crashed. Failure is detected
> by the **absence** of expected communication, not by an announcement. The
> controller detects broker liveness through the cluster's broker/controller
> communication mechanism.

### 📌 Broker vs Controller — the distinction that matters

```
+------------------------+-------------------------------+-------------------------------+
| Dimension              | Broker (data plane)           | Controller (control plane)    |
+========================+===============================+===============================+
| Handles                | produce, consume, store,      | leader assignment, broker     |
|                        | replicate                     | membership, metadata,         |
|                        |                               | partition state               |
+------------------------+-------------------------------+-------------------------------+
| Touches message bytes  | Yes                           | No                            |
+------------------------+-------------------------------+-------------------------------+
| Knows who leads P2     | Learns it from metadata       | Decides it                    |
+------------------------+-------------------------------+-------------------------------+
```

⚙️ Modern Kafka deployments can use **separate** controller roles or **combined**
broker/controller roles, depending on configuration.

---

## Part 10: Failure Handling

```
+===================================================================+
|                    PART 10 - FAILURE HANDLING                     |
+===================================================================+
```

### 💡 The one-line summary to memorize

```
+---------------------+-----------------------------+-------------------------------------+
| What died           | Who reacts                  | What happens                        |
+=====================+=============================+=====================================+
| Broker              | KRaft controller            | Partition leader election           |
| Consumer            | Group coordinator           | Consumer group rebalance            |
+---------------------+-----------------------------+-------------------------------------+
```

These are **different problems handled by different components.** Conflating them
is the most common way to get this question wrong.

### 🔄 What happens when a broker dies

Starting state:

```
  P0
  Broker 1  ->  Leader
  Broker 2  ->  Replica
  Broker 3  ->  Replica
```

Broker 1 crashes:

```
  1. Controller detects the broker failure       (missed heartbeats)
           |
  2. Controller determines: P0 needs a new leader
           |
  3. It selects an eligible replica               (must be in the ISR)
           |
              Broker 2  ->  New Leader
              Broker 3  ->  Replica
           |
  4. Metadata is updated
           |
  5. Producers/consumers refresh metadata and
     start communicating with Broker 2
```

> 💡 **The important point:** the controller does **not** move every message
> manually. It coordinates leadership and replica state; the **brokers** handle
> the actual data replication. The controller is a coordinator, not a data path.

### 🔄 What happens when a consumer dies

A different problem entirely — no leader election is involved.

```
  BEFORE                C2 dies              AFTER
  ------                -------              -----
  P0 -> C1                [X]                P0 -> C1
  P1 -> C2                                   P1 -> C3
  P2 -> C3                                   P2 -> C3
```

```
  1. Consumer group coordination detects the failure
           |
  2. A rebalance occurs
           |
  3. Partitions are reassigned to surviving consumers
           |
  4. The new owner continues from the group's committed offsets
```

Nothing about the *data* changed. Only *who is reading it* changed.

---

## Part 11: Performance, Why Kafka Is Fast

```
+===================================================================+
|             PART 11 - PERFORMANCE: WHY KAFKA IS FAST              |
+===================================================================+
```

### 📌 Why Kafka is so fast at writes

```
+---+------------------------+--------------------------------------------------+
| # | Mechanism              | Why it wins                                      |
+===+========================+==================================================+
| 1 | Append-only log        | Sequential disk writes, never random             |
| 2 | OS page cache          | Writes hit memory; disk flush is async           |
| 3 | Batching               | Fewer syscalls, better compression               |
| 4 | Partitioning           | Spreads load across partitions, brokers, disks   |
| 5 | Minimal broker logic   | Just append + serve + replicate                  |
+---+------------------------+--------------------------------------------------+
```

**1. Append-only log** — no random writes. Always append at the end. Sequential
disk writes are *fast*, even on spinning disks.

**2. OS page cache** — Kafka relies on the OS cache rather than managing its own.
Writes hit memory first; the disk flush happens asynchronously. This is also
where **zero-copy optimizations** come in.

**3. Batching** — producers send batches, not single messages, giving fewer
syscalls, better compression and higher throughput. The batch is flushed on
whichever of `batch.size` or `linger.ms` trips first, and the **sticky
partitioner** is what keeps those batches dense for unkeyed records — see
[Part 3](#part-3-topics-and-partitions).

**4. Partitioning** — writes are spread across partitions, brokers and disks.

**5. Minimal broker logic** — the broker deliberately does **not**:

```
  [X]  deserialize messages
  [X]  apply business logic
  [X]  filter per consumer

  [OK] just: append + serve + replicate
```

### 📌 How Kafka handles so many reads

Same reasons as writes, plus one structural advantage:

```
  - Sequential disk reads
  - Page cache
  - No message deletion per read
  - Consumers read independently
```

💡 **1000 consumers reading the same data?**

```
  Disk read ONCE.
  Memory read MANY times.
```

Because Kafka never deletes on read and never maintains per-consumer copies, the
hot end of the log sits in page cache and every consumer is served from RAM.
Adding readers costs almost nothing.

---

## Part 12: Scaling and Operational Reality

```
+===================================================================+
|              PART 12 - SCALING & OPERATIONAL REALITY              |
+===================================================================+
```

### ⚙️ The three scaling levers

```
+-------------------+------------------------+--------------------------------------------+
| Scale this        | Example                | What it actually buys you                  |
+===================+========================+============================================+
| Brokers           | 3 -> 6                 | More cluster resources (CPU, disk, net)    |
| Partitions        | 3 -> 12                | More partition-level parallelism           |
| Consumers         | 3 -> 12                | Nothing beyond the partition count         |
+-------------------+------------------------+--------------------------------------------+
```

**Scale brokers** (3 -> 6) — gives you more cluster resources.

**Scale partitions** (`orders`: 3 -> 12) — gives more partition-level parallelism.

**Scale consumers** (3 -> 12) — ⚠️ **only useful up to the available partition
parallelism.** Adding a 13th consumer to a 12-partition topic does not make it
faster; that consumer sits idle, because a partition can be assigned to at most
one consumer in a group (see [Part 7](#part-7-consumers-and-consumer-groups)).

⚠️ And remember from [Part 3](#part-3-topics-and-partitions): increasing the
partition count is not free — it re-maps keys and breaks per-key ordering across
the change.

### 💡 What Kafka actually costs you

Kafka is not a drop-in queue. These are the things you now own, permanently:

```
  [ ]  Partitions you must size up front
  [ ]  Consumer groups + rebalancing
  [ ]  Offset + commit semantics
  [ ]  Lag monitoring (nobody builds it up front, everybody needs it)
  [ ]  Retention policy + the storage bill that follows from it
  [ ]  Brokers to run and upgrade
```
