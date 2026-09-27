# 02 · Compute — EC2, ECS, Lambda

Where your backend code actually runs. The decision framework at the end is the
most-asked comparison in this whole document.

[← Back to index](README.md)

---

## Lambda vs ECS vs EC2 — the decision framework

**Definition**

The single most common AWS design question for a backend engineer. Interviewers are testing whether you choose on **traffic shape and control needs**, not on which service is newest.

**Diagram**

```
+----------------+----------------------------------------+----------------------------------------+
| Pick           | When                                   | Because                                |
+================+========================================+========================================+
| Lambda         | Bursty, event-driven, spiky or idle-   | Scales to zero; you pay per            |
|                | heavy traffic                          | invocation, not per idle hour          |
+----------------+----------------------------------------+----------------------------------------+
| ECS / Fargate  | Steady, containerised, long-running    | No 15-min cap, warm processes,         |
|                | services                               | container tooling you already use      |
+----------------+----------------------------------------+----------------------------------------+
| EC2            | You need full OS control, GPUs, or     | You manage the host, so you can put    |
|                | specialised hardware                   | anything on it                         |
+----------------+----------------------------------------+----------------------------------------+
```

**Example**

A CSV-validation function that fires on S3 upload belongs on Lambda.
A Flask API serving constant traffic belongs on ECS.

> **Interview point**
> Choose on traffic shape first: bursty and event-driven goes to Lambda, steady and containerised goes to ECS, and EC2 is for when you need the machine itself.


---

## EC2

**Definition**

EC2 (Elastic Compute Cloud) is a virtual server you rent to run your backend. You choose CPU, memory and storage.

**Diagram**

```
AWS  ->  EC2  ->  Linux  ->  Node.js  ->  Backend API
```

> **Interview point**
> A virtual server in AWS. Everyone knows the definition, so move quickly to how you sized, scaled and deployed it.


---

## EC2 instance types

**Definition**

Instance families map to workload profiles. The one nuance worth knowing is **burstable (t-series)** instances, which earn CPU credits while idle and spend them under load — if you exhaust credits, the instance is throttled.

**Diagram**

```
+-----------------+----------------------------+--------------------------------+
| Family          | Optimised for              | Typical use                    |
+=================+============================+================================+
| t (burstable)   | Bursty, mostly-idle load   | Dev boxes, low-traffic APIs    |
| m (general)     | Balanced CPU and memory    | Most backend services          |
| c (compute)     | CPU-bound work             | Encoding, heavy computation    |
| r (memory)      | Memory-bound work          | Caches, in-memory processing   |
+-----------------+----------------------------+--------------------------------+
```

> **Interview point**
> Match the family to the workload profile. For t-series, mention CPU credits and the throttling that follows when they run out.


---

## AMI, and AMI vs User Data

**Definition**

An AMI (Amazon Machine Image) is the immutable blueprint an EC2 instance boots from — OS plus any software baked in. The real interview question is *when to bake versus when to configure at boot.*

**Diagram**

```
+--------------------+----------------------------------------+------------------------------------+
| Approach           | What it means                          | Trade-off                          |
+====================+========================================+====================================+
| Golden AMI (bake)  | Pre-install everything into the image  | Fast, identical boots; you must    |
|                    |                                        | rebuild the image to change        |
|                    |                                        | anything                           |
+--------------------+----------------------------------------+------------------------------------+
| User Data (boot)   | Plain image, configure on first boot   | Flexible and easy to edit; slower  |
|                    |                                        | boot, can fail at launch           |
+--------------------+----------------------------------------+------------------------------------+
```

**Example**

Ubuntu AMI  ->  EC2 Instance  ->  Ubuntu  ->  Node.js  ->  Backend

> **Interview point**
> AMI is the blueprint an instance launches from. Baking a golden AMI gives fast, repeatable boots; User Data keeps the image generic but moves the risk to launch time.


---

## User Data

**Definition**

A startup script that runs **once, on first boot** (via cloud-init) to install and configure software. It is not re-run on reboot, and it is not a secrets mechanism.

**Diagram**

```
#!/bin/bash
apt update
apt install -y docker.io
docker run my-backend
```

> **Interview point**
> Bootstraps an instance at first boot. Never put secrets in it — use Secrets Manager or Parameter Store.


---

## EBS

**Definition**

EBS (Elastic Block Store) is a network-attached persistent disk for EC2. It has its own lifecycle, independent of the instance.

**Diagram**

```
EC2
 |
 +-- EBS volume
       +-- OS files
       +-- application files
       +-- logs
```

**Example**

Stop and start an instance and the EBS data is still there.

> **Interview point**
> The catch interviewers listen for: the **root volume is deleted on termination by default** unless you uncheck Delete-on-Termination. EBS persists across stop/start; instance store does not persist at all.


---

## EBS volume types and snapshots

**Definition**

`gp3` is the general-purpose SSD default; `io1`/`io2` are high-IOPS for databases; `st1`/`sc1` are throughput HDDs for big sequential workloads. Snapshots are **incremental** (only changed blocks after the first) and stored in S3.

> **Interview point**
> Pick by IOPS versus throughput need. Snapshots are incremental and S3-backed — that is the backup/DR mechanism.


---

## Stateless application design

**Definition**

The precondition that makes horizontal scaling work at all. If a request's outcome depends on state held *inside one instance*, you cannot freely add or remove instances — so ALB and Auto Scaling stop working correctly.

**Diagram**

```
            ALB
           /   \
        EC2-1   EC2-2

A file written to EC2-1's local disk is NOT on EC2-2.
The next request hits the other instance and the file is gone.
```

**Example**

Move uploads to S3 and sessions to Redis/ElastiCache, so any instance can serve any request.

> **Interview point**
> Push session and file state out of the process into a shared store (S3, Redis, the database). This is *why* ALB and Auto Scaling work — without it, scaling out breaks correctness.


---

## Lambda

**Definition**

Serverless compute that runs your code in response to an event, with no servers to manage. Event sources include S3 uploads, DynamoDB streams, API Gateway requests and CloudWatch schedules.

**Diagram**

```
Event  ->  Lambda invocation  ->  Function executes  ->  Response
```

**Example**

An S3 file upload triggers a Lambda that validates the file.

> **Interview point**
> Event-driven, stateless, short-lived compute. Good for glue, async processing and spiky APIs; bad for long-running or latency-critical always-on work.


---

## Lambda limits

**Definition**

Timeout **15 minutes** max · memory 128 MB to 10,240 MB · `/tmp` ephemeral storage up to 10 GB · concurrency and payload size limits.

> **Interview point**
> The number is trivia; the real question is the fallback. If work exceeds 15 minutes, move to Step Functions, ECS/Fargate or EC2.


---

## Lambda concurrency and scaling

**Definition**

Concurrency is the number of executions running at the same time. One Lambda instance handles exactly **one** request at a time, so N simultaneous requests means N environments.

Scaling is **burst-then-ramp**, not instant infinite scale: Lambda bursts to an initial pool, then adds capacity gradually up to your account concurrency limit.

**Diagram**

```
SIMULTANEOUS - scales out          SEQUENTIAL - reuses one
[Req 1] -> Instance #1             [Req 1] -> Instance #1
[Req 2] -> Instance #2             [Req 2] -> Instance #1 (reused)
[Req 3] -> Instance #3             [Req 3] -> Instance #1 (reused)
```

**Example**

```
+--------------------------+--------------------------------------------------+
| Setting                  | What it does                                     |
+==========================+==================================================+
| Reserved concurrency     | Caps (and guarantees) capacity for one function  |
| Provisioned concurrency  | Pre-warms environments to remove cold starts     |
+--------------------------+--------------------------------------------------+
```

> **Interview point**
> Lambda bursts then ramps — it is not instantly unlimited. Reserved concurrency caps a function; provisioned concurrency pre-warms it. Watch out that 100 parallel Lambdas means 100 database connections.


---

## Lambda cold start

**Definition**

When no warm environment exists, AWS provisions one before your handler runs, adding latency. Compiled runtimes suffer more than interpreted ones.

**Diagram**

```
Go            50 - 100 ms
Python / Node 150 - 300 ms

An idle environment typically stays warm ~45-60 minutes.
```

> **Interview point**
> Caused by provisioning a new execution environment. Mitigate with provisioned concurrency, or SnapStart for Java.


---

## Lambda + SQS

**Definition**

Lambda polls an SQS queue and is invoked with batches of messages. On success the messages are deleted; on failure they become visible again and are retried.

**Diagram**

```
Producer  ->  SQS  ->  Lambda  ->  Process message
```

> **Interview point**
> The standard pattern for asynchronous, decoupled, retryable background work. Pair it with a DLQ so poison messages stop blocking the queue.


---

## ECS

**Definition**

ECS (Elastic Container Service) is AWS's container orchestrator — it schedules containers, replaces failed ones, and wires them into load balancers, so you don't hand-manage Docker on a box.

**Diagram**

```
Docker Image  ->  ECR  ->  ECS  ->  Container running
```

> **Interview point**
> The orchestrator, not the runtime. It handles placement, health and rolling deploys across a cluster.


---

## ECS hierarchy — cluster, service, task, task definition

**Definition**

This is where candidates mix up terminology, so be precise.

**Diagram**

```
+------------------+----------------------------------------------+-----------------+
| Term             | What it is                                   | Analogy         |
+==================+==============================================+=================+
| Task definition  | Blueprint: image, CPU, memory, ports, env    | The class       |
|                  | vars, IAM role                               |                 |
+------------------+----------------------------------------------+-----------------+
| Task             | One running instance of that blueprint       | The object      |
+------------------+----------------------------------------------+-----------------+
| Service          | Keeps N tasks running, replaces failures,    | The supervisor  |
|                  | wires to ALB                                 |                 |
+------------------+----------------------------------------------+-----------------+
| Cluster          | Logical grouping of capacity the tasks run   | The pool        |
|                  | on                                           |                 |
+------------------+----------------------------------------------+-----------------+
```

**Example**

ECS Service desiredCount = 3
   Task 1   Task 2   Task 3

Task 2 crashes -> the Service starts a replacement Task 4.

> **Interview point**
> Task definition is the blueprint, task is the running instance, service maintains the desired count and handles deploys, cluster is the capacity they run on.


---

## Fargate vs EC2 launch type

**Definition**

Two ways to provide the capacity ECS tasks run on.

**Diagram**

```
+------------+-----------------------------------+---------------------------------+
|            | ECS on EC2                        | ECS on Fargate                  |
+============+===================================+=================================+
| Servers    | You manage them                   | AWS manages them                |
| Scaling    | Two layers: tasks AND instances   | One layer: tasks only           |
| Cost       | Pay for the whole instance        | Pay per task, per second        |
| Control    | GPU, custom AMI, EBS              | No GPU, limited customisation   |
+------------+-----------------------------------+---------------------------------+
```

**Example**

With ECS on EC2, scaling tasks 2 -> 4 can leave tasks PENDING for 2-5 minutes while a new EC2 instance boots and joins the cluster. Engineers then keep idle 'slack' capacity running 24/7 to hide that delay — and pay for it. Fargate removes that second layer entirely.

> **Interview point**
> Fargate removes the capacity layer: you stop managing instances and stop paying for idle headroom. Choose EC2 launch type when you need GPUs, a custom AMI, or tighter cost control at steady high volume.


---

## ECR

**Definition**

ECR is AWS's private Docker registry. IAM handles auth, and ECS/EKS/Lambda pull images from it.

**Diagram**

```
docker build  ->  docker push  ->  ECR  ->  ECS pulls the image
```

> **Interview point**
> Push the image to ECR, ECS pulls it. See [your deployment](06-my-project-deployment.md) for the real pipeline.
