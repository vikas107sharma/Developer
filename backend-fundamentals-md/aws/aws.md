# AWS for Backend Engineers

> Depth here is proportional to tier: Tier 1 topics keep their full explanation
> and diagrams, Tier 2 is trimmed to essentials, Tier 3 is one or two lines.
>
> **Legend:** 📌 Definition · ⚙️ Config · 💡 Best practice · ⚠️ Pitfall · 🔄 Flow

---

## Table of Contents

| Part | Topic |
|------|-------|
| 0 | [How This Document Is Weighted](#part-0-how-this-document-is-weighted) |
| 1 | [IAM, Identity and Access](#part-1-iam-identity-and-access) |
| 2 | [VPC, The Network Structure](#part-2-vpc-the-network-structure) |
| 3 | [Connectivity and Network Security](#part-3-connectivity-and-network-security) |
| 4 | [EC2, Compute](#part-4-ec2-compute) |
| 5 | [EBS and Stateless Design](#part-5-ebs-and-stateless-design) |
| 6 | [EC2 Networking](#part-6-ec2-networking) |
| 7 | [Load Balancing and Auto Scaling](#part-7-load-balancing-and-auto-scaling) |

---

## Part 0: How This Document Is Weighted

```
+===================================================================+
|              PART 0 - HOW THIS DOCUMENT IS WEIGHTED               |
+===================================================================+
```

```
  TIER 1   Must know - full depth and diagrams kept
           IAM, IAM Role, Trust Policy, Permissions Policy, IAM Policy,
           Temporary Credentials, VPC, CIDR, Subnets, Public vs Private Subnet,
           Availability Zones, Route Tables, Internet Gateway, Security Groups,
           NAT Gateway, EC2, EBS, Private IP, ALB, Target Groups,
           Health Checks, Auto Scaling, Stateless Application Design

  TIER 2   Know properly - trimmed to the essential point
           IAM User, IAM Group, Lambda Execution Role, IAM Least Privilege,
           EC2 Instance Types, AMI, EBS Snapshots, Public IP, Elastic IP,
           ENI, User Data, NACL, VPC Endpoints, VPC Peering, Bastion Host

  TIER 3   Basic awareness - one or two lines, no diagrams
           EBS Volume Types, AWS Client VPN, Advanced ENI,
           Advanced NACL Configuration, Advanced AMI Creation,
           Detailed EC2 Instance Families, Advanced VPC Networking
```

⚠️ **Not covered by these notes** (in the tier list, absent from the source):
`IAM Least Privilege` (Tier 2, 5-star), `EBS Snapshots` (Tier 2), and
`EBS Volume Types` (Tier 3). Worth filling in later.

---

## Part 1: IAM, Identity and Access

```
+===================================================================+
|                  PART 1 - IAM: IDENTITY & ACCESS                  |
+===================================================================+
```

### 📌 The question IAM answers — Tier 1

**Who can do what on which AWS resource?**

```
  Who
   |
   |  wants to perform
   v
  What action
   |
   |  on
   v
  Which resource
   |
   |  under
   v
  Which conditions?
```

### 📌 IAM identities — Tier 2

**IAM User** — a long-lived identity for a person or application.

```
  IAM User
     |
     +-- username
     +-- password       -> console access
     +-- access keys    -> programmatic access
```

**IAM Group** — simply a collection of IAM users.

```
  Backend Developers
        |
        +-- Vikas
        +-- Developer A
        +-- Developer B
```

### 📌 IAM Role — Tier 1

An IAM role is an AWS identity with permissions, but unlike a typical IAM user
it is **not permanently associated with one person** and has **no long-term
credentials**.

When the role is assumed, AWS provides **temporary security credentials**.

```
  EC2
   |
   v
  Backend application
   |
   v
  IAM Role
   |
   v
  Temporary credentials
```

💡 Imagine an app on an EC2 instance that needs to read user profile pictures
from an S3 bucket. The EC2 server automatically gets short-term temporary keys
from AWS behind the scenes — **you hardcode no passwords or access keys in your
application code.**

### 📌 A role has TWO sides — Tier 1

This is the part people miss. An IAM role carries both:

```
                   IAM Role
                      |
            +---------+---------+
            |                   |
            v                   v
     Trust Policy        Permissions Policy
            |                   |
            v                   v
     WHO can assume?      WHAT can they do?
            |                   |
            v                   v
        EC2 service         s3:GetObject
```

```
+----------------------+----------------------------------------+------------------+
| Side                 | Question it answers                    | Example          |
+======================+========================================+==================+
| Trust policy         | Who is allowed to assume this role?    | EC2 service      |
| Permissions policy   | What can they do once assumed?         | s3:GetObject     |
+----------------------+----------------------------------------+------------------+
```

Assigning the role to EC2 is like clipping a badge onto the server:

```
  Role
    |
    +-- attached policies
              |
              +-- permissions
```

### 📌 IAM Policy — Tier 1

A policy is **JSON describing permissions** — the document that grants or denies
specific actions on specific resources.

### 📌 Lambda execution role — Tier 2

An execution role assigned to a Lambda function, giving it temporary permissions
to access other AWS services while the function runs.

---

## Part 2: VPC, The Network Structure

```
+===================================================================+
|                PART 2 - VPC: THE NETWORK STRUCTURE                |
+===================================================================+
```

### 📌 What is a VPC? — Tier 1

A VPC is your **logically isolated network in AWS** — it securely isolates and
controls networking.

```
  AWS
  |
  +-- VPC
       |
       +-- Public Subnet
       |
       +-- Private Subnet
```

A typical backend sits behind it like this:

```
  Internet
     |
     v
    ALB
     |
     v
  Private EC2/ECS
     |
     v
  Private RDS
```

### 📌 CIDR — Tier 1

**CIDR** (Classless Inter-Domain Routing) is a method for allocating IP addresses
and routing IP packets. Example: `10.0.0.0/16`.

### 📌 Subnets — Tier 1

A subnet is a **smaller, segmented part of a larger network** that isolates and
organizes devices within a specific IP address range.

```
              my-vpc
              10.0.0.0/16
              100 IPs
                  |
        +---------+---------+
        |                   |
    subnet A            subnet B
    10.0.0.0/24         10.0.1.0/24
    public subnet       private subnet
    50 IPs              50 IPs
```

### 📌 Availability Zones — Tier 1

**A subnet is created inside an Availability Zone.** One subnet belongs to
exactly one AZ, which is how you spread a deployment across failure domains.

```
  Region
    |
    +-- AZ (a) --- Subnet --- Instances
    +-- AZ (b) --- Subnet --- Instances
    +-- AZ (c) --- Subnet --- Instances
```

### 🔄 How it fits together — Tier 1

```
+-----------------+   +--------------------------------+   +-------------------------------+   +----------------------+
| VPC             |   | SUBNETS (4)                    |   | ROUTE TABLES (3)              |   | NETWORK CONNECTIONS  |
| Your AWS network|   | Subnets within this VPC        |   | Route traffic to resources    |   | Connections outward  |
+-----------------+   +--------------------------------+   +-------------------------------+   +----------------------+
|                 |   |                                |   |                               |   |                      |
| +-------------+ |   |  AZ: eu-north-1a               |   | +---------------------------+ |   | +------------------+ |
| | project-vpc |====>|  +--------------------------+  |   | | project-rtb-public        |====>| | project-igw      | |
| +-------------+ |   |  | (A) subnet-public1-1a    |=====>| +---------------------------+ |   | +------------------+ |
|                 |   |  +--------------------------+  |   |                               |   |                      |
+-----------------+   |  | [A] subnet-private1-1a   |=====>| +---------------------------+ |   | +------------------+ |
                      |  +--------------------------+  |   | | project-rtb-private1-1a   |====>| | project-vpce-s3  | |
                      |                                |   | +---------------------------+ |   | +------------------+ |
                      |  AZ: eu-north-1b               |   |                               |   |                      |
                      |  +--------------------------+  |   | +---------------------------+ |   |                      |
                      |  | (B) subnet-public2-1b    |=====>| | project-rtb-private2-1b   | |   |                      |
                      |  +--------------------------+  |   | +---------------------------+ |   |                      |
                      |  | [B] subnet-private2-1b   |  |   |                               |   |                      |
                      |  +--------------------------+  |   +-------------------------------+   +----------------------+
                      +--------------------------------+
```

### 📌 Route Tables — Tier 1

A route table is a **set of rules, called routes**, that determine where network
traffic from your subnets or gateway is directed.

⚙️ **Every subnet in your VPC must be associated with a route table**, which
controls the routing for that subnet.

---

## Part 3: Connectivity and Network Security

```
+===================================================================+
|             PART 3 - CONNECTIVITY & NETWORK SECURITY              |
+===================================================================+
```

### 📌 Internet Gateway — Tier 1

An Internet Gateway allows communication between instances in your VPC and the
internet.

```
                                +-----------------------+
                                |       INTERNET        |
                                +-----------------------+
                                            ^
                                            |
                                            v
+-----------------------------------------------------------------------------------+
| REGION                                                                            |
|                                                                                   |
|   +---------------------------------------------------------------------------+   |
|   | VPC                                                                       |   |
|   |                                                                           |   |
|   |                         +-------------------+                             |   |
|   |                         | INTERNET GATEWAY  |                             |   |
|   |                         +-------------------+                             |   |
|   |                                   ^                                       |   |
|   |                                   |                                       |   |
|   |   +-------------------+   +---------------+   +-------------------+       |   |
|   |   | SUBNET            |   | SUBNET        |   | SUBNET            |       |   |
|   |   |                   |   |               |   |                   |       |   |
|   |   |   +-----------+   |   | +-----------+ |   |   +-----------+   |       |   |
|   |   |   | INSTANCES |   |   | | INSTANCES | |   |   | INSTANCES |   |       |   |
|   |   |   +-----------+   |   | +-----------+ |   |   +-----------+   |       |   |
|   |   +-------------------+   +---------------+   +-------------------+       |   |
|   |             |                     |                     |                 |   |
|   |   +-------------------+   +---------------+   +-------------------+       |   |
|   |   | AVAILABILITY ZONE |   | AVAILABILITY  |   | AVAILABILITY ZONE |       |   |
|   |   |        (a)        |   |   ZONE (b)    |   |        (c)        |       |   |
|   |   +-------------------+   +---------------+   +-------------------+       |   |
|   |                                                                           |   |
|   +---------------------------------------------------------------------------+   |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

### 📌 NAT Gateway — Tier 1

Enables instances in a **private subnet** to connect **out** to the internet or
other AWS services, but **prevents the internet from initiating connections** to
those instances.

💡 The everyday case: your private instance needs to download a package, so it
must reach the outside world without being reachable from it.

```
                         +-----------------------+
                         |       INTERNET        |
                         +-----------------------+
                                     ^
                                     |
                                     v
+-----------------------------------------------------------------+
| REGION                                                          |
|                                                                 |
|   +---------------------------------------------------------+   |
|   | VPC                                                     |   |
|   |                                                         |   |
|   |                  +-------------------+                  |   |
|   |                  | INTERNET GATEWAY  |                  |   |
|   |                  +-------------------+                  |   |
|   |                            ^                            |   |
|   |                            | (Downloading Updates)      |   |
|   |                            |                            |   |
|   |   +------------------------+-----------------------+    |   |
|   |   | SUBNET                                         |    |   |
|   |   |                                                |    |   |
|   |   |   +-----------+         +------------------+   |    |   |
|   |   |   | INSTANCES | ------> |   NAT GATEWAY    |   |    |   |
|   |   |   +-----------+         |  (Egress/Out)    |   |    |   |
|   |   |                         +------------------+   |    |   |
|   |   +------------------------------------------------+    |   |
|   |                                                         |   |
|   |   +------------------------------------------------+    |   |
|   |   | AVAILABILITY ZONE                              |    |   |
|   |   +------------------------------------------------+    |   |
|   |                                                         |   |
|   +---------------------------------------------------------+   |
|                                                                 |
+-----------------------------------------------------------------+
```

### 📌 Security Groups — Tier 1

A Security Group is a **virtual firewall** controlling inbound and outbound
traffic. It attaches to a **particular instance** / network interface — inside a
VPC there is a subnet, inside the subnet an instance, and the security group acts
on that instance.

```
                               +-------------------+
                               |        WWW        |
                               |    (Internet)     |
                               +-------------------+
                                   |           ^
                   Inbound Traffic |           | Outbound Traffic
                                   v           |
                       +-------------------------------+
                       |        SECURITY GROUP         |
                       |    (Virtual Instance-Level    |
                       |           Firewall)           |
                       +-------------------------------+
                                   |           ^
                                   v           |
                       +-------------------------------+
                       |          EC2 INSTANCE         |
                       |      [===] [===] [===]        |
                       +-------------------------------+
```

⚙️ **A worked configuration.** Security groups can reference *each other*, which
is how you keep an instance off the public internet entirely:

```
  Internet                    ALB Security Group
     |                        Inbound: 443 from Internet
     |  TCP 443
     v
  +-------------+
  |     ALB     |
  +-------------+
     |                        EC2 Security Group
     |  TCP 8080              Inbound: 8080 from ALB Security Group
     v
  +-------------+
  |     EC2     |
  +-------------+
```

💡 **Security groups are stateful.** If traffic is allowed in one direction,
return traffic is automatically allowed as part of the established connection.

### 📌 Network ACLs — Tier 2

An optional layer of security acting as a firewall for **one or more subnets**,
supporting both **Allow and Deny** rules.

💡 The contrast to hold: security groups act at the **instance** level and are
**stateful**; NACLs act at the **subnet** level and take **Allow or Deny** rules.

### 📌 VPC Endpoints — Tier 2

Privately connects your VPC to supported AWS services via **AWS PrivateLink**,
bypassing the Internet Gateway entirely.

```
  +-----------------------------------+
  | VPC                               |
  |   +---------------------------+   |
  |   | SUBNET                    |   |
  |   |   +-------------------+   |   |
  |   |   |     INSTANCES     |   |   |
  |   |   +-------------------+   |   |
  |   |             |             |   |
  |   |             v             |   |      PrivateLink
  |   |   +-------------------+   |   |   (no Internet Gateway)
  |   |   |   VPC ENDPOINT    |===+===+=========>  AWS S3
  |   |   +-------------------+   |   |
  |   +---------------------------+   |
  +-----------------------------------+
```

### 📌 VPC Peering — Tier 2

A networking connection between two VPCs that lets you route traffic between
them **privately**.

```
  +-----------+    Private Peering    +-----------+
  |   VPC A   |<=====================>|   VPC B   |
  | Subnets & |      Connection       | Subnets & |
  | Instances |                       | Instances |
  +-----------+                       +-----------+
```

### 📌 Bastion Host — Tier 2

A special-purpose instance in a **public** subnet that provides secure access to
your instances in **private** subnets.

```
  Internet
     |
     v
  +------------------+   private    +------------------+
  | PUBLIC SUBNET    |  connection  | PRIVATE SUBNET   |
  | Bastion instance |<============>| Instances        |
  +------------------+              +------------------+
```

### 📌 AWS Client VPN — Tier 3

Managed VPN service giving remote workers secure access to VPC resources and
on-premises networks over OpenVPN clients, through an encrypted TLS tunnel.

---

## Part 4: EC2, Compute

```
+===================================================================+
|                       PART 4 - EC2: COMPUTE                       |
+===================================================================+
```

### 📌 What is EC2? — Tier 1

EC2 (Elastic Compute Cloud) lets you **rent virtual servers** in the cloud. Those
virtual servers are called **instances**.

```
  AMI
   |
   v
  EC2 Instance
   |
   v
  Operating System
   |
   v
  Your Application
```

A concrete stack:

```
  Ubuntu AMI
      |
  EC2 instance
      |
  Ubuntu Linux
      |
    Docker
      |
  Node.js container
      |
   Backend API
```

⚙️ **What you configure at launch:**

```
  Network Settings : VPC, subnet, public or private IP
  IAM Role         : permissions to reach other AWS resources
  User Data        : scripts executed when the instance starts
  Elastic IP       : optional static public IP for consistent access
```

### 📌 Instance types — Tier 2

An EC2 instance isn't simply "a VM" — you choose its hardware characteristics.

```
  EC2 instance
   +-- CPU
   +-- Memory
   +-- Network capacity
   +-- Storage characteristics
```

### 📌 AMI — Tier 2

**AMI = Amazon Machine Image** — the blueprint/template used to create EC2
instances.

```
  Ubuntu AMI  ->  EC2 Instance  ->  Ubuntu Linux
```

### 📌 User Data — Tier 2

A startup script provided when launching an instance.

```bash
#!/bin/bash

apt update
apt install -y docker.io
docker run my-backend
```

```
  Launch EC2 -> Boot OS -> User Data executes -> Install software -> Start app
```

💡 This is what makes **automatic** instance creation useful — every instance an
Auto Scaling Group launches runs the same User Data, so it comes up already
configured.

---

## Part 5: EBS and Stateless Design

```
+===================================================================+
|                  PART 5 - EBS & STATELESS DESIGN                  |
+===================================================================+
```

### 📌 EBS — Tier 1

**EBS = Elastic Block Store.** It provides **block storage** that can be attached
to an EC2 instance.

💡 The split that makes this click:

```
+---------+----------------------------------------------------------+
| Piece   | What it actually is                                      |
+=========+==========================================================+
| EC2     | The CPU and RAM - the computing brain                    |
| EBS     | A virtual hard drive plugged in over a fast network      |
|         | cable                                                    |
+---------+----------------------------------------------------------+
```

```
             EC2
              |
       +------+------+
       |             |
      CPU           EBS
                    Disk
```

The volume holds the whole filesystem — OS, application and logs alike:

```
  EC2
   |
   +-- EBS volume
         |
         +-- OS files          EBS
         +-- application files  |
         +-- logs/files         +-- /
                                     +-- etc/
                                     +-- var/
                                     +-- home/
                                     +-- ...
```

⚙️ When you boot an EC2 instance, AWS plugs an EBS hard drive into it — its
**root filesystem is typically backed by EBS**, so the OS (like Ubuntu), your
apps and your system files all live on that EBS drive. The volume is persistent
storage: if an instance is stopped and started, the EBS data generally remains.

### ⚠️ Stateless Application Design — Tier 1

This is why backend engineers care about the above. Suppose your application
writes directly to the EC2 disk:

```
  /uploads/file.csv
```

Now put that behind a load balancer:

```
            ALB
           /   \
        EC2-1   EC2-2
```

**A file uploaded to EC2-1 isn't automatically present on EC2-2.** The next
request hits the other instance and the file is simply not there.

💡 That is why production applications generally use **shared / object storage
such as S3** instead of the instance's own disk. Keep the instances
interchangeable — anything written locally is lost the moment the request lands
elsewhere, or the instance is replaced by Auto Scaling.

---

## Part 6: EC2 Networking

```
+===================================================================+
|                      PART 6 - EC2 NETWORKING                      |
+===================================================================+
```

### 📌 Private IP — Tier 1

A private IP is used for communication **inside the VPC**.

```
  EC2-1                    EC2-2
  10.0.1.10  ---------->   10.0.1.11
              private
              network
```

### 📌 Public IP — Tier 2

A public IP allows the instance to communicate with the public internet, subject
to routing and security controls.

⚠️ In a production architecture you generally **don't** want every backend EC2
instance directly exposed to the internet. Put a load balancer in front:

```
  AVOID                 PREFER

  Internet              Internet
     |                     |
     v                     v
  Public IP               ALB
     |                     |
     v                     v
    EC2                Private EC2
```

### 📌 Elastic IP — Tier 2

A **static** public IPv4 address associated with AWS resources such as an EC2
instance.

```
+----------------------+----------------------------------------+
| Address type         | Behaviour across stop/start            |
+======================+========================================+
| Regular public IP    | Can change - a new IP is generated     |
| Elastic IP           | Stays the same - static public IPv4    |
+----------------------+----------------------------------------+
```

### 📌 ENI — Tier 2

**ENI = Elastic Network Interface** — the virtual network interface/card through
which an EC2 instance connects to the VPC.

```
  EC2
   |
   +-- ENI
        +-- Private IP
        +-- Security Groups
        +-- Network connectivity
```

📌 Security Groups attach here — see
[Part 3](#part-3-connectivity-and-network-security).

---

## Part 7: Load Balancing and Auto Scaling

```
+===================================================================+
|              PART 7 - LOAD BALANCING & AUTO SCALING               |
+===================================================================+
```

### 📌 EC2 + Load Balancer — Tier 1

One of the most important EC2 architectures for backend engineers. Instead of
exposing an instance directly, production commonly looks like:

```
                  Internet
                     |
                     v
                    ALB
                     |
            +--------+--------+
            v                 v
          EC2-1             EC2-2
            |                 |
            +--------+--------+
                     v
                    RDS
```

### 📌 Target Groups — Tier 1

The ALB needs to know **which servers should receive this traffic**. That is the
job of a Target Group.

```
  ALB
   |
   v
  Target Group
   |
   +-- EC2-1
   +-- EC2-2
   +-- EC2-3
```

### 📌 Health Checks — Tier 1

```
              ALB
              |
       +------+------+
       v             v
    EC2-1          EC2-2
    healthy        unhealthy
       |
       v
    receives
    traffic
```

💡 Your backend should expose a health endpoint, for example `GET /health`.
An instance that fails its check stops receiving traffic.

### 📌 Auto Scaling — Tier 1

AWS can automatically adjust the number of EC2 instances based on configured
conditions.

```
             Auto Scaling Group
                     |
          +----------+----------+
          v          v          v
        EC2-1      EC2-2      EC2-3
```

🔄 The loop in practice:

```
  High traffic
      |
  CPU/utilization increases
      |
  Launch another EC2
      |
  Register it with the target group
      |
  ALB sends traffic to it
```
