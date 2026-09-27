# 06 · My Project Deployment

Your own systems. This is the highest-value section in the whole set — "tell me how
you deployed it" is asked in nearly every interview, and a specific, confident answer
about real infrastructure beats any amount of service trivia.

[← Back to index](README.md)

---

## Cashier Service — ECS deployment

**Definition**

A Flask service, containerised and run on ECS behind an ALB.

**Diagram**

```
Developer  -- git push/merge -->  Git Repository
                                       |  manual deployment
                                       v
                                 Build Machine
                                       |  docker build
                                       v
                                 Docker Image
                                       |  docker push
                                       v
                                 Amazon ECR
                                       |  update-service --force-new-deployment
                                       v
                                 ECS Service  ->  New ECS Task
                                                        |
                                                        v
                                                 Flask Container :5000
```

**Example**

Runtime architecture:

```
Internet -> ALB (HTTPS :443) -> Target Group -> ECS Service -> ECS Task
                                                                  |
                                                        Flask Container :5000
```

The ALB health-checks `GET /healthcheck` and routes only to healthy tasks.
The container runs the Cashier, Collection and Cheque-Bounce APIs, OCR, NEFT/UPI and DMS sync.

Preprod repository: `preprod_blockedit_cashier`, deployed on the `latest` tag.

> **Interview point**
> "The service is containerised with Docker. We build the image on our build machine and push it to ECR, then update the ECS service with `--force-new-deployment`, which starts a new task from the latest image. An ALB receives HTTPS traffic and routes it to healthy ECS tasks."
> 
> Be ready for the follow-up: deploying on the `latest` tag means you cannot tell which image a task is running, and rollback is not deterministic — immutable tags per commit would fix it.


---

## filevalidator — Lambda deployment

**Definition**

A container-image Lambda, built and deployed through SAM from a Bitbucket pipeline.

**Diagram**

```
Developer  -- git push/merge -->  Bitbucket Repository
                                       |  manually trigger pipeline
                                       v
                                 Bitbucket Pipeline
                                       |  SSH
                                       v
                                 Bastion Host
                                       |  SSH
                                       v
                                 Build Server
                                       |  sam build -> docker build
                                       v
                                 Lambda Container Image
                                       |  push
                                       v
                                 Amazon ECR
                                       |  sam deploy
                                       v
                                 CloudFormation  ->  AWS Lambda
```

**Example**

What triggers it at runtime:

```
S3 File Upload -> S3 Event -> Lambda -> filevalidator.lambda_handler
```

The image contains the Python runtime, dependencies and `filevalidator.py`. The `.py` file is never uploaded to Lambda on its own — Lambda runs the image from ECR.

> **Interview point**
> "Our Lambda uses the container-image deployment model. After merge we trigger the Bitbucket pipeline, which connects to the build server where `sam build` reads the SAM template and builds the image with Docker. The image goes to ECR, and `sam deploy` uses CloudFormation to point the function at it."


---

## The distinction to remember

**Definition**

Both paths end at ECR — what differs is what consumes the image.

**Diagram**

```
+------------+--------------------------+----------------------------------+
|            | ECS (Cashier)            | Lambda (filevalidator)           |
+============+==========================+==================================+
| Build      | docker build             | sam build -> docker build        |
| Registry   | ECR                      | ECR                              |
| Deploy     | ecs update-service       | sam deploy -> CloudFormation     |
| Trigger    | HTTP via ALB             | S3 event                         |
+------------+--------------------------+----------------------------------+
```

**Example**

ECS    : Code -> Docker Build -> ECR -> ECS
Lambda : Code -> SAM Build -> Docker Build -> ECR -> CloudFormation -> Lambda

> **Interview point**
> SAM does not produce a different kind of image — a Lambda container image is still a container image. SAM just orchestrates the Lambda-specific build and deploy around it.
