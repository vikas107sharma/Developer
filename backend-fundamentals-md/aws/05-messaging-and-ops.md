# 05 · Messaging and Operations — SQS, SNS, CloudWatch, Secrets

[← Back to index](README.md)

---

## SQS

**Definition**

A managed queue that decouples a producer from a consumer and absorbs traffic spikes. Delivery is **at-least-once**, which means your consumer must be idempotent — processing the same message twice must be safe.

**Diagram**

```
Producer  ->  SQS  ->  Consumer
```

**Example**

The order service drops a task on the queue; a worker processes it later, so a slow worker never blocks the API.

> **Interview point**
> Decouples services and absorbs spikes. Say **at-least-once**, and that duplicates are therefore the consumer's problem to handle.


---

## Standard vs FIFO

**Definition**



**Diagram**

```
+--------------+------------------------+--------------------------------+
|              | Standard               | FIFO                           |
+==============+========================+================================+
| Throughput   | Very high              | Lower                          |
| Ordering     | Not guaranteed         | Strict, per message group      |
| Delivery     | At-least-once          | Exactly-once processing        |
+--------------+------------------------+--------------------------------+
```

> **Interview point**
> FIFO when order and deduplication matter; Standard when throughput does.


---

## Visibility timeout, DLQ and idempotency

**Definition**

When a consumer receives a message, SQS hides it for the **visibility timeout**. Delete it before that expires or it reappears and is redelivered.

After a configured number of failed receives, the message moves to a **Dead Letter Queue** instead of blocking the queue forever.

**Diagram**

```
Receive  ->  hidden (visibility timeout)  ->  process  ->  delete
         \-> timeout expires -> visible again -> retried
         \-> maxReceiveCount exceeded -> DLQ
```

**Example**

Set the visibility timeout longer than your worst-case processing time, or you will process the same message twice while the first attempt is still running.

> **Interview point**
> Three things together: visibility timeout stops double-processing, the DLQ isolates poison messages, and idempotent consumers make retries safe. A DLQ with no replay path is just a graveyard.


---

## Long polling

**Definition**

The consumer waits up to 20 seconds for a message instead of returning an empty response immediately.

**Diagram**

```
Short poll:  Poll -> empty, Poll -> empty, Poll -> message
Long poll :  Poll -> wait ............. -> message
```

> **Interview point**
> Cuts empty receives, which cuts both latency and API cost.


---

## SNS, and SQS vs SNS

**Definition**

SNS is push-based pub/sub: one message fans out to many subscribers (SQS queues, Lambda, HTTP endpoints, email).

**Diagram**

```
+-------------+----------------------------+--------------------------------+
|             | SQS                        | SNS                            |
+=============+============================+================================+
| Model       | Queue, point-to-point      | Pub/sub, fan-out               |
| Direction   | Consumer pulls             | SNS pushes                     |
| Consumers   | One consumer per message   | Every subscriber gets a copy   |
+-------------+----------------------------+--------------------------------+
```

**Example**

The **fan-out pattern**: SNS topic -> several SQS queues, so each service gets its own durable copy and processes at its own pace.

> **Interview point**
> SQS is a queue for decoupling; SNS is pub/sub for fan-out. They are commonly combined — SNS to multiple SQS queues.


---

## EventBridge

**Definition**

A serverless event bus that routes events to targets based on **content filtering rules**, so you do not write routing code.

**Diagram**

```
Application  ->  EventBridge  ->  rules  ->  SQS / Lambda / Step Functions
```

> **Interview point**
> Use it when different event types must reach different consumers and you want the routing declared as rules rather than coded.


---

## CloudWatch

**Definition**

The observability service — how you find out your service broke.

**Diagram**

```
+-----------+--------------------------------+--------------------------------------+
| Piece     | What it is                     | Used for                             |
+===========+================================+======================================+
| Logs      | Application and platform logs  | Debugging; query with Logs Insights  |
+-----------+--------------------------------+--------------------------------------+
| Metrics   | Numeric time series            | Dashboards, scaling triggers         |
+-----------+--------------------------------+--------------------------------------+
| Alarms    | Threshold on a metric          | Notify via SNS, trigger auto scaling |
+-----------+--------------------------------+--------------------------------------+
```

> **Interview point**
> Logs to investigate, metrics to observe, alarms to be told. Alarms are also what drives Auto Scaling.


---

## Secrets Manager vs Parameter Store

**Definition**

How your service gets database credentials and config in production. This comes up often and is usually missing from prep notes.

**Diagram**

```
+------------+--------------------------------+------------------------------------+
|            | Secrets Manager                | SSM Parameter Store                |
+============+================================+====================================+
| Rotation   | Built-in automatic rotation    | None natively                      |
| Cost       | Priced per secret              | Free standard tier                 |
| Best for   | DB passwords, API keys         | Config values, non-rotating        |
|            |                                | secrets                            |
+------------+--------------------------------+------------------------------------+
```

> **Interview point**
> Secrets Manager when you need rotation; Parameter Store for plain config. Either way the app reads them at startup through its IAM role — nothing is baked into the image or committed.


---

## CloudFormation and IaC

**Definition**

Infrastructure as Code means declaring infrastructure in version-controlled templates instead of clicking in the console. CloudFormation is the AWS-native option; Terraform is the multi-cloud one.

> **Interview point**
> Mostly owned by DevOps in practice. Know what it is and that you have worked alongside it — the depth is rarely probed for a backend role.
