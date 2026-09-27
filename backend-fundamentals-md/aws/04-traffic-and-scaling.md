# 04 · Traffic and Scaling — ALB, Auto Scaling, Route 53, CloudFront

[← Back to index](README.md)

---

## Elastic Load Balancing — ALB vs NLB

**Definition**

ELB distributes incoming traffic across healthy targets. For backend work you need two of the three types.

**Diagram**

```
+-------------+--------------------------------+----------------------------------+
|             | ALB                            | NLB                              |
+=============+================================+==================================+
| Layer       | 7 (HTTP/HTTPS/gRPC)            | 4 (TCP/UDP/TLS)                  |
| Routes on   | Path, host, headers            | Connection only                  |
| Strength    | Content-aware routing, TLS     | Ultra-low latency, static IP     |
| Use for     | REST APIs, microservices       | Raw throughput, non-HTTP         |
+-------------+--------------------------------+----------------------------------+
```

**Example**

api.example.com/users  -> ALB -> Users Service
api.example.com/orders -> ALB -> Orders Service

> **Interview point**
> ALB is Layer 7 and routes on content; NLB is Layer 4 for raw throughput and static IPs. Pick NLB when you need performance or a non-HTTP protocol, ALB when you need routing intelligence.
> 
> (A third type, Gateway Load Balancer, fronts third-party security appliances — worth naming, not worth studying.)


---

## Target Groups

**Definition**

The pool the load balancer routes to — EC2 instances, IP addresses, ECS tasks or Lambda functions. It owns the health-check configuration, and it is separate from the load balancer so you can swap groups for blue/green deploys.

**Diagram**

```
ALB  ->  Target Group  ->  EC2-1 / EC2-2 / ECS Task
```

> **Interview point**
> The routable pool plus its health-check config. Decoupled from the load balancer, which is what makes blue/green swaps possible.


---

## Health checks — and what /health should actually do

**Definition**

The load balancer polls each target and stops sending traffic to any that fails. The question interviewers actually probe is what your endpoint checks.

An endpoint that returns 200 unconditionally is close to useless — the process is up, but the service may be unable to do anything.

**Diagram**

```
+-------------------+----------------------------+-------------------------------+
| Endpoint style    | Checks                     | Problem                       |
+===================+============================+===============================+
| return 200        | Process is alive           | Passes while the DB is down   |
+-------------------+----------------------------+-------------------------------+
| Dependency-aware  | DB, cache, disk reachable  | Correct, but can cascade      |
+-------------------+----------------------------+-------------------------------+
```

**Example**

ALB
  EC2-1  200 OK   -> receives traffic
  EC2-2  timeout  -> removed from rotation
  EC2-3  200 OK   -> receives traffic

> **Interview point**
> Check real dependencies, not just liveness. Then mention the trade-off: if every instance fails health checks because one shared database is down, you have taken the whole service out — so decide deliberately whether to fail open or closed.


---

## Horizontal vs vertical scaling

**Definition**

**Horizontal** adds more instances or tasks. **Vertical** makes one instance bigger. Backends prefer horizontal because it also buys availability.

**Diagram**

```
Horizontal  1 instance  ->  5 instances
Vertical    2 CPU/4 GB  ->  8 CPU/16 GB
```

> **Interview point**
> Scale out, not up — one bigger box is still one failure domain. This only works if the app is stateless.


---

## Auto Scaling

**Definition**

An Auto Scaling Group keeps the instance count between a minimum and maximum, driven by CloudWatch alarms. ECS scales tasks the same way.

**Diagram**

```
+------------+------------------------------------+
| Setting    | Meaning                            |
+============+====================================+
| Minimum    | Never go below this                |
| Desired    | Target right now                   |
| Maximum    | Never go above this                |
+------------+------------------------------------+
```

**Example**

CPU > 70%  ->  3 tasks  ->  5 tasks  ->  8 tasks
An instance crashes  ->  the ASG launches a replacement.

> **Interview point**
> Target-tracking policies are the usual choice over step scaling. Two things to add: **lifecycle hooks** let you drain connections before an instance is removed, and none of it is safe unless the app is stateless.


---

## Load balancer vs Auto Scaling

**Definition**

Two different jobs that get conflated.

**Diagram**

```
Load Balancer  ->  decides WHERE traffic goes
Auto Scaling   ->  decides HOW MANY instances exist
```

> **Interview point**
> One routes, the other provisions. They cooperate: Auto Scaling registers new instances with the target group, and the balancer starts using them once they pass health checks.


---

## Scaling stops at the database

**Definition**

An important system-design point. The application tier scales horizontally; the database usually does not.

**Diagram**

```
ALB -> API 1 / API 2 / API 3  ->  RDS   <- the bottleneck
```

**Example**

More API instances means more connections and more queries against one database, until RDS becomes the limit.

> **Interview point**
> Adding API servers does not add database capacity. The fixes are connection pooling, read replicas, caching, query and index tuning, and moving work to a queue.


---

## Route 53

**Definition**

AWS's DNS service: it resolves a hostname to a destination. That is a different job from load balancing.

**Diagram**

```
api.example.com  ->  Route 53 (DNS)  ->  ALB (HTTP routing)  ->  ECS tasks
```

**Example**

An **Alias** record points at AWS resources such as an ALB and works at the zone apex (example.com), where a CNAME is not allowed.

> **Interview point**
> DNS routing is not HTTP routing. Route 53 answers 'which destination does this hostname resolve to?'; the ALB answers 'which healthy target gets this request?'. Know Alias vs CNAME; routing policies (weighted, latency, failover, geolocation) are worth naming only.


---

## API Gateway

**Definition**

A managed front door for APIs — it receives client requests and forwards them to Lambda, ECS or any HTTP backend, adding auth, throttling and stages.

**Diagram**

```
Client  ->  API Gateway  ->  Lambda / ECS / HTTP backend
```

**Example**

```
+--------------+----------------------------------------------+
| Feature      | What it gives you                            |
+==============+==============================================+
| Auth         | IAM, JWT, Cognito, Lambda authorizers        |
| Throttling   | Rate limits that protect your backend        |
| Stages       | dev / staging / prod deployments             |
| CORS         | Which browser origins may call the API       |
+--------------+----------------------------------------------+
```

> **Interview point**
> API Gateway manages APIs; an ALB balances load. API Gateway + Lambda is the serverless pairing; ALB + ECS is the container pairing.


---

## CloudFront

**Definition**

A CDN that caches content at edge locations near users, cutting latency and origin load. Origins are typically S3, an ALB or EC2.

**Diagram**

```
Viewer  ->  Edge Location  ->  Regional Edge Cache  ->  Origin (S3 / ALB)
```

**Example**

Static assets cache by default. Dynamic responses cache only if you configure TTLs and cache behaviours; user-specific data should not be cached.

> **Interview point**
> Caches at the edge to reduce origin load. On invalidation: it is slow and billed, so the better practice is **versioned filenames** (`app.v2.js`) rather than invalidating paths.
