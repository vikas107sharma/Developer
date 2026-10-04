+-----------------------------------------------------------------------------------------+
| NODE.JS APP DEPLOYMENT ARCHITECTURE                                                     |
+-----------------------------------------------------------------------------------------+

  +--------+         +------------------+                    +-----------------+
  |        |         |   EC2 INSTANCE   |   (Pushes Image)   |   AMAZON ECR    |
  | GITHUB | =======>|  (Build Server)  | =================> |   (Registry)    |
  | (Code) | (Pulls) |  +------------+  |                    +-----------------+
  +--------+         |  | Docker CLI |  |                            |
                     |  +------------+  |                            | (Pulls Image)
                     +------------------+                            v
                               ^                             +-----------------+
                               | (Grants permission          |   AMAZON ECS    |
                               |  to push/auth to ECR)       |   (Cluster /    |
                     +------------------+                    |   Containers)   |
                     |     AWS IAM      |                    +-----------------+
                     | (Instance Role)  |                            |
                     +------------------+                            | (Streams Logs)
                                                                     v
                                                             +-----------------+
                                                             | AWS CLOUDWATCH  |
                                                             | (Observability) |
                                                             +-----------------+


CORE COMPONENTS

EC2 (Build Host): Pulls code and builds the Docker image.

IAM: Grants EC2 permissions to authenticate and push to ECR securely.

ECR: Private registry storing Docker images.

ECS: Orchestrates and runs container tasks across cluster resources.

Task Definition: Container blueprint (image URI, CPU/RAM, ports, env vars).

CloudWatch: Collects and streams container application logs.

DEPLOYMENT STEPS

Authenticate Docker to ECR:
aws ecr-public get-login-password --region us-east-1 | docker login --username AWS --password-stdin public.ecr.aws/e3i3d3z5

Build Docker Image:
docker build -t node-app .

Tag Image:
docker tag node-app:latest public.ecr.aws/e3i3d3z5/node-app:latest

Push to ECR:
docker push public.ecr.aws/e3i3d3z5/node-app:latest

Deploy:
Update ECS Service to roll out tasks using the new ECR image tag.

Are there two EC2 instances here?
Yes, conceptually there are two different compute roles:EC2 Instance #1 (Build Machine): An ephemeral machine used strictly to pull code from GitHub, build the Docker image, and push it to ECR.   EC2 Instance #2 (Runtime Worker): An EC2 instance registered inside the ECS cluster that actually runs the Node.js container application.


+-------------------------------------------------------------------------------------------------+
| BUILD & PUSH PHASE (Build Machine)                                                              |
+-------------------------------------------------------------------------------------------------+
|   GitHub =======> [ EC2 Instance #1 ] =======(docker push)=======> Amazon ECR                   |
|   (Code)          (Build Server)                                   (Image Registry)             |
+-------------------------------------------------------------------------------------------------+
                                                                            |
                                                                            | (Pulls Image)
                                                                            v
+-------------------------------------------------------------------------------------------------+
| RUNTIME & ORCHESTRATION PHASE (ECS Cluster)                                                     |
+-------------------------------------------------------------------------------------------------+
|   AWS ECS CONTROL PLANE (AWS Managed Master Node - Schedules & Monitors)                        |
|                                                                                                 |
|   +------------------------------------------------------------------------------------------+  |
|   | ECS CLUSTER (Worker Capacity Pool)                                                       |  |
|   |                                                                                          |  |
|   |   +----------------------------------------------------------------------------------+   |  |
|   |   | [ EC2 Instance #2 ] (Host VM registered to Cluster)                              |   |  |
|   |   |                                                                                  |   |  |
|   |   |   +---------------------------------------+                                      |   |  |
|   |   |   | ECS Agent                             |                                      |   |  |
|   |   |   +---------------------------------------+                                      |   |  |
|   |   |   | Docker Container (Running Node.js)    | =====(Logs)=====> AWS CloudWatch     |   |  |
|   |   |   +---------------------------------------+                                      |   |  |
|   |   +----------------------------------------------------------------------------------+   |  |
|   +------------------------------------------------------------------------------------------+  |
+-------------------------------------------------------------------------------------------------+


ECS Data Plane (Where containers run):

EC2 Mode: The containers do run inside EC2 instances that belong to your ECS Cluster. ECS installs an agent on your EC2 instance to start/stop Docker containers on it.

Fargate Mode: Containers run on AWS-managed serverless infrastructure (no EC2 instances for you to manage).



+-----------------------------------------------------------------------------------------------------------------+
| AWS CLOUD                                                                                                       |
| +-------------------------------------------------------------------------------------------------------------+ |
| | REGION                                                                                                      | |
| | +-----------------------------------------------------------------------+ +-------------------------------+ | |
| | | VPC 1 (NETWORK)                                                       | | VPC 2 (NETWORK)               | | |
| | | +-------------------------------------------------------------------+ | |                               | | |
| | | | AVAILABILITY ZONE (AZ)                                            | | |   [ EC2 ]     [ EC2 ]         | | |
| | | |                                                                   | | |                               | | |
| | | |   +-------------------------+     +---------------------------+   | | |   [ EC2 ]     [ EC2 ]         | | |
| | | |   | PUBLIC SUBNET           |     | PRIVATE SUBNET            |   | | |                               | | |
| | | |   |                         | NAT |                           |   | | |  (Isolated Network)           | | |
| | | |   |   [ EC2 ]     [ EC2 ]   |====>|   [ DB EC2 ]   [ DB EC2 ] |   | | +-------------------------------+ | |
| | | |   | (Web/App)   (Web/App)   |     |  (Database)    (Database) |   | |                                   | |
| | | |   +-------------------------+     +---------------------------+   | |                                   | |
| | | +-------------------------------------------------------------------+ |                                   | |
| | +-----------------------------------------------------------------------+                                   | |
| +-------------------------------------------------------------------------------------------------------------+ |
+-----------------------------------------------------------------------------------------------------------------+
        ^
        | (Internet Traffic via Internet Gateway)
   [ USER ]


+------------------------------------------+
|               AWS REGION                 |
+------------------------------------------+
| VPC 1                                    |
|                                          |
|  [ INTERNET GATEWAY (IGW) ]              |
|                ^                         |
|  [ ROUTE TABLE ]                         |
|  - 0.0.0.0/0  => IGW                     |
|  - 10.0.0.0/16 => Local                  |
|                ^                         |
|  +------------------------------------+  |
|  | PUBLIC SUBNET                      |  |
|  | - [ Web / App EC2 ]                |  |
|  | - [ NAT Gateway ] (Elastic IP)     |  |
|  +------------------------------------+  |
|                    ^                     |
|                    | (Outbound Traffic)  |
|  +------------------------------------+  |
|  | PRIVATE SUBNET                     |  |
|  | - [ Database EC2 ]                 |  |
|  | - [ Private Route Table ]          |  |
|  |   - 0.0.0.0/0  => NAT Gateway      |  |
|  |   - 10.0.0.0/16 => Local           |  |
|  +------------------------------------+  |
+------------------------------------------+
| VPC 2 (Isolated)                         |
| - [ EC2 Instances ]                      |
+------------------------------------------+


VPC Peering is a 1:1 network connection between two Virtual Private Clouds (VPCs) that allows traffic to route between them using private IPv4 or IPv6 addresses.

+------------------+                    +------------------+
| VPC A            |  VPC Peering Conn  | VPC B            |
| (10.1.0.0/16)    | <================> | (10.2.0.0/16)    |
|                  |                    |                  |
| [ Web Service ]  | (Private IP Flow)  | [ Shared DB ]    |
+------------------+                    +------------------+




================================================================================
EC2 TO AMAZON RDS MYSQL CONNECTION GUIDE

+-----------------------------------------------------------------------+
| VPC (vpc-c360b8a8)                                                    |
|                                                                       |
|  [ EC2 Instance ] ===== (Port 3306) =====> [ Amazon RDS MySQL ]       |
|  SG: ec2-rds-1                             SG: rds-ec2-1              |
+-----------------------------------------------------------------------+

SETUP RDS LINK:

Go to AWS RDS -> Create Database (MySQL, Standard Create).

In Connectivity, select "Connect to an EC2 compute resource".

Select EC2 instance (i-02ff15932f0fd192e).

Copy DB Endpoint: database-1.cc4jdxfcgiop.us-east-2.rds.amazonaws.com

INSTALL CLIENT ON EC2:
sudo apt update && sudo apt install -y mysql-client

CONNECT VIA CLI:
mysql -u admin -h database-1.cc4jdxfcgiop.us-east-2.rds.amazonaws.com -P 3306 -p

SECURITY GROUPS (Auto-configured):

EC2 SG (ec2-rds-1) -> Outbound Port 3306 to rds-ec2-1

RDS SG (rds-ec2-1) -> Inbound Port 3306 from ec2-rds-1