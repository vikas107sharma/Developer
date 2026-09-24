# Asynchronous Processing and Messaging Systems

> Getting work off the request path — the seven async patterns, how to choose a
> broker between Kafka, RabbitMQ, Pub/Sub and SQS, and the failure modes every
> one of them shares.
>
> **Legend:** 📌 Definition · ⚙️ Config · 💡 Best practice · ⚠️ Pitfall · 🔄 Flow

---

## Table of Contents

**Overview**

| Part | Topic |
|------|-------|
| 0 | [The Async Spectrum at a Glance](#part-0-the-async-spectrum-at-a-glance) |

**A · Async Processing Patterns**

| Part | Topic |
|------|-------|
| 1 | [Background Jobs Using Application Threads](#part-1-background-jobs-using-application-threads) |
| 2 | [Database-Based Async (Polling)](#part-2-database-based-async-polling) |
| 3 | [Cron Jobs and Scheduled Workers](#part-3-cron-jobs-and-scheduled-workers) |
| 4 | [Webhooks](#part-4-webhooks) |
| 5 | [Serverless and Task Services](#part-5-serverless-and-task-services) |
| 6 | [Message Queue](#part-6-message-queue) |
| 7 | [Event Streaming](#part-7-event-streaming) |

**B · Two Ways to Slice Messaging**

| Part | Topic |
|------|-------|
| 8 | [Message Queue vs Event Streaming](#part-8-message-queue-vs-event-streaming) |
| 9 | [Work Queue vs Pub/Sub](#part-9-work-queue-vs-pubsub) |

**C · Choosing a Broker**

| Part | Topic |
|------|-------|
| 10 | [Pub/Sub vs Kafka](#part-10-pubsub-vs-kafka) |
| 11 | [Kafka vs RabbitMQ vs SQS](#part-11-kafka-vs-rabbitmq-vs-sqs) |
| 12 | [RabbitMQ Routing](#part-12-rabbitmq-routing) |
| 13 | [SQS Standard vs FIFO](#part-13-sqs-standard-vs-fifo) |

**D · What Goes Wrong in All of Them**

| Part | Topic |
|------|-------|
| 14 | [Delivery Guarantees and the Two Generals Problem](#part-14-delivery-guarantees-and-the-two-generals-problem) |
| 15 | [Poison Messages and Dead Letter Queues](#part-15-poison-messages-and-dead-letter-queues) |
| 16 | [Backpressure](#part-16-backpressure) |

---

## Part 0: The Async Spectrum at a Glance

```
+===================================================================+
|              PART 0 - THE ASYNC SPECTRUM AT A GLANCE              |
+===================================================================+
```

📌 Every approach in Section A answers the same question — *how do I stop making
the caller wait?* They differ in what happens when something goes wrong.

```
+------------------+-----------------------+-------------------+-------------+----------------+
| Approach         | Durable?              | Real-time?        | Scales out? | Extra infra?   |
+==================+=======================+===================+=============+================+
| App threads      | No - lost on crash    | Yes               | No          | None           |
| DB polling       | Yes                   | No - poll delay   | Yes         | DB only        |
| Cron             | Yes                   | No - time-driven  | Limited     | Scheduler      |
| Webhooks         | Only with retries     | Yes               | Yes         | None (HTTP)    |
| Serverless       | Yes                   | Yes               | Automatic   | Cloud vendor   |
| Message queue    | Yes                   | Yes               | Yes         | Broker         |
| Event streaming  | Yes - and replayable  | Yes               | Yes         | Kafka cluster  |
+------------------+-----------------------+-------------------+-------------+----------------+
```

💡 Read the table top to bottom as a durability gradient. The first row loses
work on a crash; the last row still has it a week later.

---

# Section A · Async Processing Patterns

---

## Part 1: Background Jobs Using Application Threads

```
+===================================================================+
|                   PART 1 - APPLICATION THREADS                    |
+===================================================================+
```

📌 Run async work **inside the same service process**.

```
  API Thread  --submit-->  Background Thread
```

```
+-----------------------------------+-----------------------------------+
| Pros                              | Cons                              |
+===================================+===================================+
| - No extra infrastructure         | - Service crash -> jobs lost      |
| - Low latency                     | - No retries or durability        |
|                                   | - Hard to scale across machines   |
+-----------------------------------+-----------------------------------+
```

⚠️ The job lives and dies with the process. There is no record of it anywhere
else, so a deploy, an OOM kill or a crash silently destroys in-flight work.

---

## Part 2: Database-Based Async (Polling)

```
+===================================================================+
|              PART 2 - DATABASE-BASED ASYNC (POLLING)              |
+===================================================================+
```

📌 Store tasks in the database and have workers poll for them.

```
  Order Service  ---->  DB (task)
                          ^
                          |  poll
                        Worker  ---->  process
```

```
+-----------------------------------+-----------------------------------+
| Pros                              | Cons                              |
+===================================+===================================+
| - Durable - survives a crash      | - Constant polling is inefficient |
| - Easy retries                    | - High DB load                    |
+-----------------------------------+-----------------------------------+
```

⚠️ The DB becomes both your queue and your system of record. Poll frequency is a
direct trade between latency and database load, and there is no setting that
makes both good.

---

## Part 3: Cron Jobs and Scheduled Workers

```
+===================================================================+
|              PART 3 - CRON JOBS & SCHEDULED WORKERS               |
+===================================================================+
```

📌 Run tasks at fixed intervals.

```
  Cron  ---->  every 5 mins  ---->  run task
```

**Use cases:** daily reports, reminder emails, cleanup jobs.

```
+-----------------------------------+-----------------------------------+
| Pros                              | Cons                              |
+===================================+===================================+
| - Predictable                     | - Not real-time                   |
| - Simple                          | - Bad for user-triggered events   |
+-----------------------------------+-----------------------------------+
```

📌 **The defining property:** cron is **time-driven, not event-driven.** It fires
because the clock said so, never because something happened. That is exactly why
it is a poor fit for anything a user just did.

---

## Part 4: Webhooks

```
+===================================================================+
|                         PART 4 - WEBHOOKS                         |
+===================================================================+
```

📌 Your system asynchronously calls **another system's** API.

```
  Payment success  ---->  call merchant webhook
```

```
+-----------------------------------+-----------------------------------+
| Pros                              | Cons                              |
+===================================+===================================+
| - Real-time integration           | - Network failures                |
| - Event-driven                    | - Retry complexity                |
|                                   | - Receiver downtime handling      |
+-----------------------------------+-----------------------------------+
```

⚠️ Webhooks are async but **unreliable without retries and idempotency.** You are
making a network call to a system you do not control, so you own the retry
policy, the backoff, and the duplicate-delivery problem it creates. See
[Part 14](#part-14-delivery-guarantees-and-the-two-generals-problem).

---

## Part 5: Serverless and Task Services

```
+===================================================================+
|                PART 5 - SERVERLESS & TASK SERVICES                |
+===================================================================+
```

📌 Managed async execution — the provider runs the worker for you.

**Examples:** AWS Lambda, Google Cloud Tasks, Azure Functions.

```
+-----------------------------------+-----------------------------------+
| Pros                              | Cons                              |
+===================================+===================================+
| - Auto scaling                    | - Cold starts                     |
| - No server management            | - Execution time limits           |
|                                   | - Stateless by nature             |
+-----------------------------------+-----------------------------------+
```

---

## Part 6: Message Queue

```
+===================================================================+
|                      PART 6 - MESSAGE QUEUE                       |
+===================================================================+
```

📌 A broker holds work until a consumer takes it.

```
  Producer  ---->  Queue  ---->  Consumer
```

**Used for:** background jobs, retries, buffering traffic spikes.

**Example:** `Order placed  ->  send email job`

💡 RabbitMQ and SQS are the archetypes here — compared in detail in
[Part 11](#part-11-kafka-vs-rabbitmq-vs-sqs).

---

## Part 7: Event Streaming

```
+===================================================================+
|                     PART 7 - EVENT STREAMING                      |
+===================================================================+
```

📌 Events are published once, and **multiple consumers react independently.**

```
  Producer  ---->  Topic  ---->  Consumer Groups
```

Events **remain stored and can be replayed later** — the read does not destroy
the data.

💡 Kafka is the archetype — see [Part 10](#part-10-pubsub-vs-kafka).

---

# Section B · Two Ways to Slice Messaging

> Parts 8 and 9 both compare "queues" against "something else", but along
> **different axes.** Part 8 is about *what a message means* (a job vs a fact).
> Part 9 is about *how many consumers get it* (one vs all). Keep them separate.

---

## Part 8: Message Queue vs Event Streaming

```
+===================================================================+
|             PART 8 - MESSAGE QUEUE vs EVENT STREAMING             |
+===================================================================+
```

💡 The cleanest way to hold these apart:

```
  Message Queue    ->  a TODO LIST          (work to be done, then crossed off)
  Event Streaming  ->  an IMMUTABLE HISTORY (facts that happened, kept)
```

```
+----------------+---------------------------------+-----------------------------------+
| Aspect         | Message Queue (todo list)       | Event Streaming (history)         |
+================+=================================+===================================+
| Unit           | Each message = one job          | Each event = one fact             |
+----------------+---------------------------------+-----------------------------------+
| Mutability     | Consumed and discarded          | Immutable, never rewritten        |
+----------------+---------------------------------+-----------------------------------+
| Consumers      | One consumer processes it       | Many can read the same event      |
+----------------+---------------------------------+-----------------------------------+
| After reading  | Message removed                 | Retained for the retention period |
+----------------+---------------------------------+-----------------------------------+
| Replay         | No                              | Yes                               |
+----------------+---------------------------------+-----------------------------------+
| Examples       | Send email, generate invoice,   | OrderPlaced, PaymentCompleted,    |
|                | resize image                    | UserSignedUp                      |
+----------------+---------------------------------+-----------------------------------+
| Good for       | Task processing, worker systems | Analytics, auditing, real-time    |
|                |                                 | pipelines                         |
+----------------+---------------------------------+-----------------------------------+
```

📌 **Message Queue (todo list)** — each message is one job, one consumer
processes it, and the message is removed after processing.

📌 **Event Streaming (immutable history)** — an event is a *fact*. Events are
immutable, multiple consumers can read the same event, and events can be
replayed. They stay for the retention period **even after consumption**.

**Example:** Apache Kafka.

---

## Part 9: Work Queue vs Pub/Sub

```
+===================================================================+
|                  PART 9 - WORK QUEUE vs PUB/SUB                   |
+===================================================================+
```

📌 Two different **topologies**, often confused.

**Work queue — point-to-point.** Each message goes to exactly **one** consumer.

```
   resize-image    charge-card    send-email
        |               |              |
        v               v              v
     worker1         worker2        worker3

   3 workers, 3 messages, 1:1 -- the work is DIVIDED
```

**Pub/Sub — topic fan-out.** Each subscriber gets **its own copy**.

```
   publisher: event (order placed)
                    |
                    v
           Topic (order placed)
                    |
        +-----------+-----------+
        |           |           |
        v           v           v
   inventory      email     analytics

   1 event, 3 copies -- the work is DUPLICATED
```

💡 Work queue **divides** work. Pub/sub **duplicates** it. Choosing the wrong one
either drops work or does it three times.

---

# Section C · Choosing a Broker

---

## Part 10: Pub/Sub vs Kafka

```
+===================================================================+
|                    PART 10 - PUB/SUB vs KAFKA                     |
+===================================================================+
```

### 📌 Classic pub/sub

```
  - push-based model
  - each subscriber gets their own copy
  - message stays until pushed to the subscriber, then removed
```

⚠️ Hard to handle when the subscriber is slow and the producer is fast — the
broker has nowhere to put the backlog. See [Part 16](#part-16-backpressure).

### 📌 Delivery model

```
+------------------+-------------------+---------------------+
| Aspect           | Pub/Sub           | Kafka               |
+==================+===================+=====================+
| Delivery         | Push              | Pull                |
| Retry            | Broker-driven     | Consumer-driven     |
| Backpressure     | Hard              | Natural             |
+------------------+-------------------+---------------------+
```

💡 Kafka consumers **pull when ready**, which gives you backpressure for free.
A slow consumer simply asks for less; it never gets flooded.

### 📌 Fan-out to multiple consumers

```
+-------------+--------------------------------+---------------------------+
|             | Pub/Sub                        | Kafka                     |
+=============+================================+===========================+
| Storage     | Broker duplicates messages     | One copy stored           |
| Consumers   | Each gets its own copy         | Many read the same data   |
| Cost        | Memory + network heavy         | Zero duplication          |
+-------------+--------------------------------+---------------------------+
```

💡 **Kafka scales reads cheaply.** Adding the tenth consumer costs almost nothing
because there is still exactly one copy on disk.

### 📌 Message lifetime

```
+---------------------+-------------------+---------------------+
| Aspect              | Pub/Sub           | Kafka               |
+=====================+===================+=====================+
| Message retention   | Until delivered   | Time / size based   |
| Replay              | No                | Yes                 |
| Late joiner         | Misses data       | Can replay          |
+---------------------+-------------------+---------------------+
```

### 📌 Consumer independence

```
  Pub/Sub :  the BROKER tracks delivery
  Kafka   :  CONSUMERS track their own offsets
```

### 📌 Throughput

Kafka is extremely fast because of:

```
  - Sequential disk writes
  - OS page cache
  - Zero-copy (sendfile)
  - Batching
  - No per-message ACK to multiple consumers
```

Pub/sub systems typically do the opposite:

```
  - Per-message routing
  - Maintain subscriber lists
  - Push data eagerly
```

### 📌 Why Kafka is not just pub/sub

Kafka **intentionally breaks** classic pub/sub assumptions:

```
  - Broker does NOT track per-consumer delivery
  - Broker does NOT delete data on consumption
  - Consumers are responsible for their own state
  - Storage is first-class, not a buffer
```

💡 Kafka is closer to **a distributed commit log + pub/sub semantics** than to a
message broker.

### 💡 When to use plain pub/sub instead

```
  - Simple notifications
  - Low-latency push
  - No need for replay
  - Few consumers
```

---

## Part 11: Kafka vs RabbitMQ vs SQS

```
+===================================================================+
|                PART 11 - KAFKA vs RABBITMQ vs SQS                 |
+===================================================================+
```

### 💡 The mental model

```
  RabbitMQ  =  smart postman
               routes messages to the right consumer,
               forgets them once delivered

  Kafka     =  append-only log
               writes everything to disk; consumers read at
               their own pace and can re-read history

  SQS       =  AWS's managed queue
               you manage nothing; AWS handles scale,
               you just push and pull
```

### 📌 Kafka vs RabbitMQ, head to head

Kafka keeps **events** (event streams). RabbitMQ works on **tasks** (a message
queue).

```
+------------------+--------------------------+---------------------------+
| Feature          | Kafka                    | RabbitMQ                  |
+==================+==========================+===========================+
| Model            | Event log                | Message broker            |
| Consumers        | Multiple, independent    | Single consumer per task  |
| Push vs Pull     | Pull (consumer polls)    | Push                      |
| Replay           | Yes                      | No                        |
| Retention        | Time-based               | Removed once task ACKed   |
| Throughput       | Very high                | Moderate                  |
| Scaling          | Horizontal               | Limited                   |
| Consumer state   | Held by the consumer     | Held by the broker        |
| Best for         | Streaming                | Tasks                     |
+------------------+--------------------------+---------------------------+
```

### ⚠️ The practical gotchas, three ways

```
+----------------------+----------------------+----------------------------+----------------------------+
| Concern              | RabbitMQ             | Kafka                      | SQS                        |
+======================+======================+============================+============================+
| Message replay       | No - once consumed,  | Yes - replay anytime       | No - once deleted, gone    |
|                      | gone                 | within retention           |                            |
+----------------------+----------------------+----------------------------+----------------------------+
| Ordering             | Per-queue            | Per-partition              | Only in FIFO mode (slower) |
+----------------------+----------------------+----------------------------+----------------------------+
| Max retention        | Until consumed       | Configurable (days, or     | 14 days max                |
|                      |                      | forever)                   |                            |
+----------------------+----------------------+----------------------------+----------------------------+
| Ops burden           | You run it           | You really run it - KRaft, | Zero - fully managed       |
|                      |                      | partitions, rebalancing    |                            |
+----------------------+----------------------+----------------------------+----------------------------+
| Throughput ceiling   | ~50K msg/sec         | Millions msg/sec           | Effectively unlimited      |
|                      |                      |                            | (Standard); FIFO is capped |
|                      |                      |                            | - see Part 13              |
+----------------------+----------------------+----------------------------+----------------------------+
| Cost model           | Server cost          | Server cost, storage heavy | Pay per request            |
+----------------------+----------------------+----------------------------+----------------------------+
| Push vs Pull         | Push to consumer     | Pull by consumer           | Pull (long-polling)        |
+----------------------+----------------------+----------------------------+----------------------------+
| Multi-consumer, same | Via fanout exchange  | Native (consumer groups)   | Need SNS + SQS fanout      |
| message              |                      |                            |                            |
+----------------------+----------------------+----------------------------+----------------------------+
```

### 📌 Where each one actually wins

**RabbitMQ wins when** (~50k msg/sec):

```
  - You need complex routing
      (this message goes to queue A and B, that one only to C)
  - Per-message acknowledgment matters (task queues, job processing)
  - You want priority queues, delayed messages and dead-letter
    queues out of the box
  - Low-to-medium throughput (tens of thousands msg/sec)

  Example: order processing pipeline, email/SMS dispatch, background jobs
```

**Kafka wins when:**

```
  - High throughput (millions msg/sec)
  - Multiple consumers need to read the same stream independently
      (analytics + audit + ML pipeline all reading order events)
  - You need to replay messages
      (reprocess the last 7 days because a bug corrupted data)
  - Event sourcing, log aggregation, stream processing

  Example: clickstream tracking, financial transaction logs, CDC from databases
```

**SQS wins when** (~120k msg/sec commonly observed on Standard):

```
  - You're already on AWS and don't want to babysit infrastructure
  - Simple producer -> queue -> consumer pattern
  - Variable / spiky load (auto-scales)
  - You don't need ordering (Standard), or you need light ordering (FIFO)

  Example: decoupling Lambda functions, simple work queues,
           async API processing
```

### 💡 Quick decision shortcuts

```
+--------------------------------------------+------------------------------------+
| If you need...                             | Reach for                          |
+============================================+====================================+
| "A task queue for background jobs"         | RabbitMQ or SQS                    |
| "Stream events to 5 different systems"     | Kafka                              |
| "I'm on AWS and just want it to work"      | SQS                                |
| "Replay last week's events"                | Kafka (others can't)               |
| "Complex routing rules"                    | RabbitMQ                           |
| "1M+ events/sec"                           | Kafka, no contest                  |
| "Delayed / scheduled messages, easily"     | RabbitMQ or SQS (Kafka is awkward  |
|                                            | here)                              |
+--------------------------------------------+------------------------------------+
```

### 📌 One-liner summary

> **RabbitMQ** for work distribution · **Kafka** for event streaming and replay ·
> **SQS** for managed simplicity on AWS.

---

## Part 12: RabbitMQ Routing

```
+===================================================================+
|                    PART 12 - RABBITMQ ROUTING                     |
+===================================================================+
```

📌 RabbitMQ is *the one with the routing.* A topic exchange matches an incoming
routing key against every binding, and delivers to all that match.

```
   INCOMING ROUTING KEY:  orders.eu.priority
              |
              v
       +---------------+
       | TOPIC EXCHANGE|
       +-------+-------+
               |
     +---------+-------------+-------------+
     |                       |             |
     v                       v             v
  BINDING                 BINDING       BINDING
  orders.*.priority       orders.eu.*   orders.#
     |                       |             |
   MATCHED                 MATCHED       MATCHED
```

💡 Reach for RabbitMQ when **the routing is the interesting part** — background
jobs, workflows, per-message control.

### ⚠️ RabbitMQ: a consumed message is gone

```
  consumer A  ->  acknowledges  ->  message is deleted
  consumer B  ->  arrives       ->  sees an empty queue
```

In Kafka, a consumed message is **still there**. Each consumer has its own
pointer and decides where to start.

```
  Kafka     ->  replay history
  RabbitMQ  ->  rich routing
  SQS       ->  on AWS, want zero ops
```

---

## Part 13: SQS Standard vs FIFO

```
+===================================================================+
|                  PART 13 - SQS: STANDARD vs FIFO                  |
+===================================================================+
```

### 📌 Benefits of SQS over Kafka

**Zero operational burden.** SQS is fully serverless — no brokers, no
ZooKeeper/KRaft, no partitions to size.

**Cost at low volume.** Pay-per-request (first 1M requests/month free, then
~$0.40/M). Kafka has a fixed floor — an MSK cluster costs money 24/7 even at zero
traffic.

**Built-in retry + DLQ semantics.** Visibility timeout, per-message redelivery
and DLQ-after-N-failures are native. In Kafka you build all of this yourself
(retry topics, DLQ topics, offset management around poison messages) — see
[Part 15](#part-15-poison-messages-and-dead-letter-queues).

**Simpler consumer model.** Receive -> process -> delete. No consumer groups, no
offsets, no rebalancing storms, no partition assignment.

**Effortless consumer scaling.** Add pollers freely; SQS handles distribution.
Kafka caps parallelism at the partition count.

### ⚠️ What you give up

```
  - No replay. Once a message is deleted, it's gone.
  - One consumer per message, no fan-out. SQS is a work queue.
  - Throughput and payload ceilings. 256 KB max message size.
```

### ⚙️ Standard vs FIFO

```
+--------------+--------------------------+-----------------------------------+
|              | STANDARD (throughput     | FIFO (order first)                |
|              | first)                   |                                   |
+==============+==========================+===================================+
| Delivery     | At-least-once            | Exactly-once processing (within   |
|              |                          | the dedup window)                 |
+--------------+--------------------------+-----------------------------------+
| Ordering     | Best-effort              | Strict                            |
+--------------+--------------------------+-----------------------------------+
| Throughput   | Effectively unlimited    | 300 TPS baseline per API action;  |
|              |                          | 3,000 msg/sec with batching; up   |
|              |                          | to ~70k msg/sec in high-          |
|              |                          | throughput mode                   |
+--------------+--------------------------+-----------------------------------+
```

⚙️ **Deduplication** happens on the *enqueue* side, over a **5-minute window.**

⚠️ Visibility timeout still applies on consume, so **your consumer still needs to
be idempotent.** If you don't delete the message before its visibility timer
expires, SQS hands it back to another consumer.

---

# Section D · What Goes Wrong in All of Them

---

## Part 14: Delivery Guarantees and the Two Generals Problem

```
+===================================================================+
|           PART 14 - DELIVERY GUARANTEES & TWO GENERALS            |
+===================================================================+
```
```
+-----------------+-----------------------------+--------------------------+
| Guarantee       | What it means               | The catch                |
+=================+=============================+==========================+
| At most once    | Fire and forget             | Drops are acceptable     |
| At least once   | Retry until acknowledged    | Duplicates possible      |
| Exactly once    | Promised by marketing       | Look closely - see below |
+-----------------+-----------------------------+--------------------------+
```

### ⚠️ Exactly-once delivery is not achievable

Exactly-once **delivery** across a network is not achievable in general —
**neither in Kafka, RabbitMQ, nor SQS.**

This is closely related to the **Two Generals Problem**, a classical
impossibility result.

### 🔄 The acknowledgement problem

```
  Producer  --- message --->  Broker
  Producer  <--- ACK -------  Broker
                  |
                  X   ACK lost in the network

  The producer is now confused:

    Option 1: retry            ->  may cause a duplicate
    Option 2: drop the message ->  may lose it

  There is no third option. The producer cannot tell the two cases apart.
```

### 💡 What "exactly once" actually means

```
  exactly once  =  at least once  +  idempotent processing
```

You never get exactly-once *delivery*. You get exactly-once *effect*, by making
the receiving side safe to call twice.

---

## Part 15: Poison Messages and Dead Letter Queues

```
+===================================================================+
|          PART 15 - POISON MESSAGES & DEAD LETTER QUEUES           |
+===================================================================+
```

### ⚠️ One bad message freezes everything

A single **poison message** retrying infinitely can take down a pipeline handling
millions of good messages a minute.

```
  [poison msg]  ->  fail  ->  retry  ->  fail  ->  retry  ->  ...
                                |
                                v
              the whole partition / queue stalls behind it
```

**The fix:** a **Dead Letter Queue** — after N failures, move the message aside
so the pipeline keeps flowing.

💡 A DLQ **without a replay path is a graveyard.** Moving the message out of the
way is only half the job; you also need a way to fix and reprocess it.

---

## Part 16: Backpressure

```
+===================================================================+
|                      PART 16 - BACKPRESSURE                       |
+===================================================================+
```

### ⚠️ The 3:45 a.m. scenario

The broker is out of memory — **not because of a bug**, but because the producer
is producing far faster than the consumer consumes.

```
  Producer  10k msg/sec
  Consumer   2k msg/sec
  ---------------------
  Delta      8k msg/sec  ->  piles up, forever
```

### ⚠️ "Nothing broke" is not a defence

The messages did get processed — three hours later. **An answer that arrives
three hours late is simply no answer.**

### 📌 The three backpressure strategies

```
+------------------+--------------------------------+--------------------------------+
| Strategy         | How it works                   | What it costs                  |
+==================+================================+================================+
| Drop messages    | Cap the queue size (bounded    | You lose messages - but you    |
|                  | queues). Once the hard cap is  | lose them loudly and           |
|                  | reached, raise                 | predictably.                   |
|                  | QueueFullException back to the |                                |
|                  | producer.                      |                                |
+------------------+--------------------------------+--------------------------------+
| Auto-scale       | Add consumers until they keep  | 20 consumers all hammer the DB |
| consumers        | up.                            | - the bottleneck just moves to |
|                  |                                | the DB.                        |
+------------------+--------------------------------+--------------------------------+
| Credit-based     | The consumer tells the         | Most correct, most work to     |
| flow control     | producer how many messages it  | implement.                     |
|                  | can take.                      |                                |
+------------------+--------------------------------+--------------------------------+
```

💡 Every strategy is a choice about *where* to feel the pain. Backpressure does
not make the load go away — it decides who absorbs it.
