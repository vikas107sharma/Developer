# 03 · Data and Storage — S3, RDS, DynamoDB, ElastiCache

[← Back to index](README.md)

---

## S3

**Definition**

Object storage: buckets hold objects addressed by a **key**. There are no real folders — `uploads/orders/2026/file.csv` is the whole key, slashes included.

**Diagram**

```
Bucket  +  Object Key  +  Object Data  +  Metadata

PutObject / GetObject / DeleteObject / HeadObject
```

**Example**

Backend  ->  PutObject  ->  s3://my-company-files/csv/orders/2026/file.csv

> **Interview point**
> Object storage, not a filesystem. The key is a flat string; the folder structure is an illusion.


---

## S3 presigned URLs

**Definition**

A temporary, signed URL that grants access to **one specific object** for a limited time, without giving the client any AWS credentials. Your backend generates it with its own IAM permissions.

The reason it matters is load: without it, every byte of every upload and download flows through your API servers.

**Diagram**

```
WITHOUT presigned URL              WITH presigned URL
Client -> Backend -> S3            Client -> Backend (returns URL only)
  (all bytes through your API)     Client ----------> S3  (bytes direct)
```

**Example**

A user uploads a 2 GB video. Your backend returns a presigned PUT URL and the browser uploads straight to S3 — your API never touches the file.

> **Interview point**
> Temporary scoped access without sharing credentials. Say the *why*: it keeps large uploads and downloads off your application servers.


---

## S3 event notifications

**Definition**

S3 can emit an event when an object changes, triggering downstream processing.

**Diagram**

```
File uploaded  ->  S3 ObjectCreated event  ->  Lambda / SQS / SNS / EventBridge
```

**Example**

orders.csv lands in S3  ->  event  ->  SQS  ->  worker parses the CSV.

> **Interview point**
> The standard way to react asynchronously to uploads instead of polling.


---

## S3 storage classes, lifecycle, replication, consistency

**Definition**

**Classes:** Standard, Standard-IA, One Zone-IA, Glacier, Intelligent-Tiering — trade retrieval speed and cost against access frequency.

**Lifecycle policies** move or expire objects automatically by age. **Replication** (SRR/CRR) copies objects between buckets and needs versioning on both. **Consistency** has been strong read-after-write since December 2020.

> **Interview point**
> Match the class to the access pattern. Note that S3 is now strongly consistent — many older prep sources still wrongly say eventual.


---

## RDS

**Definition**

Managed relational database (MySQL, PostgreSQL, MariaDB). AWS handles installation, backups, patching, monitoring and failover; you still own schema, queries, indexes and users.

> **Interview point**
> Removes the operational work of running the database yourself. You still own everything above the engine.


---

## Multi-AZ vs Read Replica

**Definition**

The pairing interviewers use most, and the one candidates most often get backwards. They solve different problems.

**Diagram**

```
+---------------+---------------------------------+---------------------------------+
|               | Multi-AZ                        | Read Replica                    |
+===============+=================================+=================================+
| Purpose       | High availability               | Read scaling                    |
+---------------+---------------------------------+---------------------------------+
| Replication   | Synchronous                     | Asynchronous (lag is possible)  |
+---------------+---------------------------------+---------------------------------+
| Serves reads  | No - standby is idle            | Yes                             |
+---------------+---------------------------------+---------------------------------+
| Endpoint      | Same endpoint after failover    | Separate endpoint               |
+---------------+---------------------------------+---------------------------------+
| Failover      | Automatic                       | Manual promotion                |
+---------------+---------------------------------+---------------------------------+
```

**Example**

Multi-AZ answers 'what if my database dies?'
Read Replica answers 'how do I handle more reads?'

> **Interview point**
> Multi-AZ is synchronous standby for availability and fails over on the same endpoint. A read replica is asynchronous, has its own endpoint, and must be promoted manually.


---

## RDS connection management

**Definition**

Every connection costs the database memory. A backend must not open a connection per request — use a pool.

**Diagram**

```
100 API requests  ->  Connection Pool (N connections)  ->  RDS
```

**Example**

Total connections = instances x pool size. Ten ECS tasks with a pool of 20 is 200 connections — enough to exhaust a small RDS instance.

> **Interview point**
> Use pooling, and remember the total is instances x pool size. Blindly raising the pool size is how you take RDS down. RDS Proxy exists for Lambda, where concurrency multiplies connections.


---

## Aurora

**Definition**

AWS's MySQL/PostgreSQL-compatible engine that separates **compute from storage**. Storage is distributed across AZs; a cluster has one writer and multiple readers with automated failover.

**Diagram**

```
Application  ->  Aurora Cluster
                  Writer Instance      Reader Instance
                        Shared Aurora Storage
```

> **Interview point**
> Same interface as RDS, cloud-native storage underneath — faster failover and easier read scaling.


---

## DynamoDB

**Definition**

Fully managed NoSQL key-value/document store with single-digit millisecond latency. You design around **access patterns**, not around normalised tables and joins.

**Diagram**

```
Partition Key   Sort Key    Attributes
   userId        orderId    name, amount, status
     101          5001      Vikas, 500, PAID
     101          5002      Vikas, 800, PENDING
```

> **Interview point**
> Key-value at scale. Choose it over RDS when you know your access patterns and need predictable latency; choose RDS when you need joins, ad-hoc queries or multi-row ACID.


---

## Partition key design and hot partitions

**Definition**

The partition key decides which physical partition holds an item, so it decides how your traffic spreads. A low-cardinality key concentrates traffic on one partition — a **hot partition** — and that partition throttles even though the table has spare capacity.

Each partition is capped at roughly **3,000 RCU / 1,000 WCU**.

**Diagram**

```
BAD   PK = country     -> 'INDIA' takes 90% of traffic -> throttled
GOOD  PK = userId      -> traffic spreads across partitions
```

**Example**

If a key is unavoidably hot, use **write sharding**: append a suffix (`INDIA#1` ... `INDIA#10`) to spread writes, and query all shards on read.

> **Interview point**
> Pick a high-cardinality key so load spreads. The senior follow-up is 'what breaks first?' — a hot partition throttling at ~3,000 RCU / 1,000 WCU while the table looks under-used.


---

## Query vs Scan

**Definition**

**Query** targets one partition key and is efficient. **Scan** reads every item in the table and then filters.

**Diagram**

```
Query  userId = 101   ->  reads only that partition
Scan                  ->  reads ALL items, then filters
```

> **Interview point**
> Always prefer Query. A FilterExpression on a Scan does not make it cheap — DynamoDB reads and bills for the items first, then filters.


---

## GSI, capacity and consistency

**Definition**

A **GSI** gives the same data a second query path under a different partition key. **Capacity** is on-demand (AWS manages it) or provisioned (you set RCU/WCU). **Reads** are eventually consistent by default, or strongly consistent on request.

**Example**

Table PK userId/orderId, plus a GSI on status/createdAt so you can query all PENDING orders.

> **Interview point**
> A GSI is another query path with its own keys and its own capacity. Strongly consistent reads are **not** available on a GSI — GSI reads are always eventually consistent.


---

## DynamoDB transactions

**Definition**

Multiple writes that succeed or fail as one atomic unit.

**Example**

Debit account A by 500 and credit account B by 500 — you must never get one without the other.

> **Interview point**
> Atomic multi-item writes, for when a partial update would corrupt state.


---

## ElastiCache (Redis)

**Definition**

Managed Redis or Memcached, normally in a private subnet, reachable on port 6379 only from your application's security group.

**Diagram**

```
App  ->  cache lookup  ->  hit?  return
                        ->  miss? read DB, write to cache, return
```

**Example**

Cache-aside is the pattern to know: read cache, on miss read the database, populate the cache, set a TTL.

> **Interview point**
> Managed Redis. Know cache-aside, TTL and eviction, and pool your connections rather than opening one per request. Redis has persistence, replication and failover; Memcached is simpler and has none of them.
