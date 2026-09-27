# AWS for Backend Engineers — Interview Notes

Every topic follows the same shape: **Definition → Diagram → Example → Interview point.**
Depth is set by how often the topic actually comes up in backend-engineer interviews,
not by how much there is to say about it.

## Files

| File | Covers |
|---|---|
| [01 · IAM and Networking](01-iam-and-networking.md) | IAM roles and policies, STS, VPC, subnets, routing, security groups, NACLs, endpoints |
| [02 · Compute](02-compute.md) | EC2, AMI, EBS, stateless design, Lambda, ECS/Fargate, and the Lambda-vs-ECS-vs-EC2 decision |
| [03 · Data and Storage](03-data-and-storage.md) | S3 and presigned URLs, RDS Multi-AZ vs read replicas, Aurora, DynamoDB, ElastiCache |
| [04 · Traffic and Scaling](04-traffic-and-scaling.md) | ALB vs NLB, target groups, health checks, Auto Scaling, Route 53, API Gateway, CloudFront |
| [05 · Messaging and Operations](05-messaging-and-ops.md) | SQS, SNS, EventBridge, CloudWatch, Secrets Manager |
| [06 · My Project Deployment](06-my-project-deployment.md) | Your Cashier ECS service and filevalidator Lambda |

---

## The whole picture

```
                         INTERNET
                             |
                             v
                         Route 53              (DNS: which destination?)
                             |
                             v
                        CloudFront             (edge cache)
                             |
                             v
                           ALB                 (HTTP routing: which healthy target?)
                             |
                    +--------+--------+
                    v                 v
                 ECS Task          ECS Task
                    |                 |
         +----------+--------+--------+
         v                   v                 v
       Redis                RDS                S3
    ElastiCache           Aurora


   ASYNC PATH                EVENT PATH              OBSERVABILITY
   Application               Application              ECS / ALB / Lambda / RDS
       |                         |                            |
       v                         v                            v
      SQS                   EventBridge                   CloudWatch
       |                    /    |    \                       |
       v                   v     v     v                       v
    Lambda               SQS  Lambda  SNS                   Alarms
       |
       v
       S3


   SECURITY
   IAM                        KMS                      Secrets Manager
    +-- ECS Role               +-- S3 encryption         +-- DB / API credentials
    +-- Lambda Role            +-- RDS encryption
    +-- EC2 Role               +-- Secrets encryption
```

---

## One-line recall

If you remember nothing else, remember these.

```
+------------------------+----------------------------------------------------------------------------+
| Topic                  | The one line                                                               |
+========================+============================================================================+
| IAM Role               | Trust policy = who can assume it; permissions policy = what it can do      |
| STS                    | Assuming a role returns short-lived credentials, so you never store keys   |
| Subnet                 | Public only because its route table sends 0.0.0.0/0 to an IGW              |
| NAT Gateway            | Outbound only; the internet can never initiate a connection in             |
| Security Group         | Instance level, allow-only, stateful                                       |
| NACL                   | Subnet level, stateless, so you must allow the return traffic too          |
| VPC Endpoint           | Reach S3/DynamoDB privately and skip the NAT charge                        |
| Lambda vs ECS vs EC2   | Choose on traffic shape: bursty, steady, or needs the machine              |
| Lambda scaling         | Bursts then ramps; 100 parallel invocations means 100 DB connections       |
| Cold start             | New execution environment; fix with provisioned concurrency                |
| ECS hierarchy          | Task definition is the blueprint, task the instance, service the           |
|                        | supervisor                                                                 |
| Fargate                | Removes the capacity layer, so no idle instance headroom to pay for        |
| Stateless design       | The precondition that makes ALB and Auto Scaling correct                   |
| EBS                    | Root volume is deleted on termination by default                           |
| Presigned URL          | Keeps large uploads and downloads off your API servers                     |
| Multi-AZ               | Synchronous standby for availability, same endpoint on failover            |
| Read Replica           | Asynchronous, own endpoint, promoted manually, for read scaling            |
| Partition key          | High cardinality, or one hot partition throttles at ~3000 RCU              |
| Query vs Scan          | Scan reads and bills for everything, then filters                          |
| GSI                    | Another query path; its reads are always eventually consistent             |
| Connection pool        | Total connections = instances x pool size                                  |
| Health check           | Check real dependencies, not just that the process is alive                |
| ALB vs NLB             | Layer 7 content routing vs Layer 4 raw throughput                          |
| Route 53 vs ALB        | DNS resolution is not HTTP routing                                         |
| SQS                    | At-least-once, so the consumer must be idempotent                          |
| DLQ                    | Isolates poison messages; useless without a replay path                    |
| SQS vs SNS             | Queue for decoupling, pub/sub for fan-out; often combined                  |
| CloudFront             | Version filenames rather than paying to invalidate                         |
| Secrets Manager        | Use it when you need rotation; Parameter Store for plain config            |
+------------------------+----------------------------------------------------------------------------+
```
