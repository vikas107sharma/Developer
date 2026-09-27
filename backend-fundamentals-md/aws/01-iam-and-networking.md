# 01 · IAM and Networking

Who is allowed to do what, and how traffic reaches your service.

[← Back to index](README.md)

---

## IAM — the model

**Definition**

IAM answers one question: **who can do what, on which resource, under which conditions?** The point for a backend engineer is that no long-lived AWS keys should ever live in your code or environment.

**Diagram**

```
Who  ->  What action  ->  Which resource  ->  Under which conditions?
```

> **Interview point**
> Centralised, fine-grained access control. The answer interviewers want is that services get permissions through **roles**, not hardcoded keys.


---

## IAM Policy — the JSON

**Definition**

Every permission in AWS is a policy document with the same four elements. Being able to sketch this on a whiteboard is a common two-minute test.

**Diagram**

```
+-------------+----------------------------------------------------+
| Element     | Meaning                                            |
+=============+====================================================+
| Effect      | Allow or Deny. An explicit Deny ALWAYS wins.       |
| Action      | The API calls, e.g. s3:GetObject                   |
| Resource    | The ARN(s) it applies to                           |
| Condition   | Optional extra constraints (IP, MFA, tags)         |
+-------------+----------------------------------------------------+
```

**Example**

{
  "Effect": "Allow",
  "Action": "s3:GetObject",
  "Resource": "arn:aws:s3:::my-bucket/*"
}

> **Interview point**
> Effect, Action, Resource, Condition — and an explicit Deny always overrides an Allow.


---

## IAM Role, and its two sides

**Definition**

A role is an identity with permissions that is **not tied to one person and has no long-term credentials**. Anything programmatic — EC2, Lambda, an ECS task — should use one.

Every role has two distinct policies, and confusing them is the classic tell that someone has only read the docs.

**Diagram**

```
+----------------------+----------------------------------------+------------------+
| Side                 | Question it answers                    | Example          |
+======================+========================================+==================+
| Trust policy         | WHO is allowed to assume this role?    | EC2 service      |
| Permissions policy   | WHAT can they do once assumed?         | s3:GetObject     |
+----------------------+----------------------------------------+------------------+
```

**Example**

An app on EC2 needs to read profile pictures from S3. The instance assumes its role and gets short-term keys automatically — nothing is hardcoded.

> **Interview point**
> Trust policy = who can assume it. Permissions policy = what it can do. Mixing these up is the most common IAM mistake.


---

## Temporary credentials (STS)

**Definition**

When something 'assumes a role', it calls `sts:AssumeRole`. STS checks the trust policy, then returns a short-lived AccessKeyId, SecretAccessKey and SessionToken (1 hour by default, 12 hours max). No permanent secret ever exists.

**Diagram**

```
Service  ->  sts:AssumeRole  ->  trust policy checked
         ->  temporary credentials (expire in ~1h)
```

> **Interview point**
> Assuming a role returns short-lived credentials from STS. That is the whole reason you never need to store AWS keys in a backend service.


---

## Least privilege

**Definition**

Grant only the specific actions on the specific resource. `dynamodb:*` on `*` is the answer that loses you the point; read-one-named-table is the answer that wins it.

**Diagram**

```
BAD   Action: dynamodb:*        Resource: *
GOOD  Action: dynamodb:GetItem  Resource: arn:aws:dynamodb:...:table/Orders
```

> **Interview point**
> Scope to the exact action and the exact ARN. Mention IAM Access Analyzer, which derives a tight policy from real CloudTrail usage.


---

## Lambda execution role

**Definition**

A Lambda function has **no credentials of its own**. At invoke time it assumes its execution role, and that role's policy is the only thing gating what the function can touch.

> **Interview point**
> Lambda assumes its execution role automatically on invoke — you never give a function keys.


---

## IAM User and Group

**Definition**

An IAM **user** is a long-term identity with permanent credentials, for a human or a legacy app. A **group** just bundles policies for several users. For anything service-to-service, prefer a role.

> **Interview point**
> Users have long-lived credentials; roles give temporary ones. Modern practice is roles for everything programmatic.


---

## Networking

## VPC

**Definition**

Your logically isolated network in AWS. Everything else — subnets, route tables, gateways, security groups — hangs off it.

**Diagram**

```
Internet  ->  ALB  ->  Private EC2/ECS  ->  Private RDS
```

> **Interview point**
> An isolated virtual network you control. Public-facing things go in public subnets, application and database tiers go in private ones.


---

## CIDR

**Definition**

The prefix length sets the block size: `/16` gives 65,536 addresses, `/24` gives 256. AWS reserves 5 IPs in every subnet.

**Diagram**

```
VPC  10.0.0.0/16
  subnet A  10.0.0.0/24   (public)
  subnet B  10.0.1.0/24   (private)
```

> **Interview point**
> Smaller prefix means a bigger block. Subnet CIDRs cannot overlap.


---

## Subnets, AZs, and public vs private

**Definition**

A subnet lives in **exactly one Availability Zone**. Crucially, a subnet is public or private because of its **route table** — not because of any flag on the subnet itself.

**Diagram**

```
+--------------------+--------------------------+------------------------------+
|                    | Public subnet            | Private subnet               |
+====================+==========================+==============================+
| 0.0.0.0/0 route    | Internet Gateway         | NAT Gateway (or none)        |
| Typical contents   | ALB, NAT GW, bastion     | App servers, ECS tasks, RDS  |
+--------------------+--------------------------+------------------------------+
```

**Example**

Spreading subnets across AZ-a, AZ-b and AZ-c means one data centre failing does not take the application down.

> **Interview point**
> A subnet is in one AZ, and it is public only because its route table points 0.0.0.0/0 at an Internet Gateway.


---

## Route Tables

**Definition**

Rules deciding where traffic leaving a subnet goes. Every subnet is associated with exactly one route table.

**Diagram**

```
PUBLIC   0.0.0.0/0  ->  Internet Gateway
PRIVATE  0.0.0.0/0  ->  NAT Gateway
```

> **Interview point**
> The 0.0.0.0/0 target is what makes a subnet public or private.


---

## Internet Gateway

**Definition**

The one-per-VPC managed door to the internet. Without a route to it, a subnet cannot be public no matter what public IPs you assign.

**Diagram**

```
EC2  ->  Route Table  ->  Internet Gateway  ->  Internet
```

> **Interview point**
> Attached to the VPC. A resource also needs a public IP and a route to actually use it.


---

## NAT Gateway

**Definition**

Lets a private-subnet resource make **outbound** connections to the internet, while the internet can never initiate a connection inward.

**Diagram**

```
Private EC2  ->  NAT Gateway  ->  Internet Gateway  ->  Internet
```

**Example**

Your private ECS task needs to pull an npm package or call a third-party payment API.

> **Interview point**
> Outbound-only. Internet Gateway = two-way for public resources; NAT Gateway = one-way out for private ones.


---

## Security Groups

**Definition**

A virtual firewall at the **instance / network-interface** level. Allow rules only, and **stateful** — if a connection is allowed in, the response is automatically allowed out.

**Diagram**

```
Internet  --443-->  ALB  --8080-->  EC2

ALB SG : allow 443 from the internet
EC2 SG : allow 8080 from the ALB's security group
```

**Example**

Referencing the ALB's security group rather than an IP range keeps the EC2 instance unreachable from the internet entirely.

> **Interview point**
> Instance-level, allow-only, stateful. Security groups can reference each other, which is how you avoid opening anything to 0.0.0.0/0.


---

## NACL, and Security Group vs NACL

**Definition**

A NACL is a firewall at the **subnet** boundary. It is **stateless**, supports explicit **Deny**, and evaluates rules in numeric order. Both layers must independently allow traffic for it to pass.

**Diagram**

```
+--------------+--------------------+----------------------------------------+
|              | Security Group     | NACL                                   |
+==============+====================+========================================+
| Level        | Instance / ENI     | Subnet                                 |
+--------------+--------------------+----------------------------------------+
| State        | Stateful           | Stateless - allow BOTH directions      |
+--------------+--------------------+----------------------------------------+
| Rules        | Allow only         | Allow and explicit Deny                |
+--------------+--------------------+----------------------------------------+
| Evaluation   | All rules          | In rule-number order, first match wins |
+--------------+--------------------+----------------------------------------+
```

> **Interview point**
> The trap is statefulness. With a NACL you must allow the return traffic explicitly; with a security group you do not. Traffic must pass both.


---

## VPC Endpoints (PrivateLink)

**Definition**

Let resources reach AWS services **without** a NAT Gateway, Internet Gateway or public IP — traffic stays on the AWS network.

**Diagram**

```
+---------------------+-----------------------+----------------------------------+
| Type                | Used for              | How                              |
+=====================+=======================+==================================+
| Gateway endpoint    | S3, DynamoDB only     | A route-table entry. Free.       |
| Interface endpoint  | Most other services   | An ENI in your subnet            |
|                     |                       | (PrivateLink).                   |
+---------------------+-----------------------+----------------------------------+
```

**Example**

A Lambda in a private subnet writing to S3 through a gateway endpoint avoids NAT Gateway data-processing charges entirely.

> **Interview point**
> Keeps traffic off the public internet and cuts NAT costs. Gateway endpoints for S3 and DynamoDB; interface endpoints for the rest.


---

## VPC Peering and Bastion Host

**Definition**

**Peering** is a private one-to-one link between two VPCs. It is **not transitive** and the CIDRs must not overlap.

A **bastion host** is a single hardened public instance used as the only SSH entry point to private instances.

> **Interview point**
> Peering is non-transitive — A-B and B-C does not give you A-C. For bastions, name **SSM Session Manager** as the modern alternative that removes the public instance and the SSH keys altogether.


---

## Private IP, Public IP and Elastic IP

**Definition**

A **private IP** is stable for the instance's life and used inside the VPC. An auto-assigned **public IP** is ephemeral — it is released on stop and a new one is assigned on start. An **Elastic IP** is a static public IP reserved to your account.

> **Interview point**
> The catch interviewers listen for: AWS charges for an Elastic IP that is allocated but **not attached** to a running instance.
