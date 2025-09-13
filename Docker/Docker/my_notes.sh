docker build -f Dockerfile.dev -t node-app-dev .

docker build -f Dockerfile.prod -t node-app-prod .

docker run -d -p 3000:3000 node-app

docker logs -f <container_id>


docker run -p 8080:3000 my-app
3000 → container port (your app is listening here inside container)
8080 → host port (you access via localhost:8080 on your machine)



docker ps and logs
Flag	Description	Example
-a	Show all containers (even stopped)	docker ps -a
-f	Follow logs in real-time	docker logs -f my-container



docker images           - show all images



docker run
Flag	Description	Example
-d	Run container in background (detached)	docker run -d nginx
-p	Map port (host:container)	docker run -p 8080:80 nginx
-e	Set environment variable	-e NODE_ENV=production



docker build
Flag	Description	Example
-f	Specify Dockerfile name	docker build -f Dockerfile.dev .
-t	Tag the image with a name	docker build -t my-app .






CONTAILERS    - Running instances of Docker images (like live processes).
Container = created using docker run

IMAGES        - Read-only templates used to create containers (like blueprints).
Image = built using docker build



docker stop <containerid>          - Stop a running container.
docker start <containerid>         - Start a stopped container.


Command	One-Line Explanation
docker pull <image>	Download image from registry.
docker run <image>  Download (if not) and run. (Docker pull + docker start)
docker build -t <name> .	Build image from Dockerfile.
docker images	List all images.
docker run -d --name <container> <image>	Run container in background.
docker ps	List running containers.
docker ps -a	List all containers (running + stopped).
docker stop <container>	Stop running container.
docker start <container>	Start stopped container.
docker rm <container>	Delete container.
docker rmi <image>	Delete image.
docker exec -it <container> bash	Enter running container terminal.
docker logs <container>	View container logs.



docker network create <name>	               - Create Docker network.
docker network ls                              - show network
docker network rm <network_name_or_id>         - remove network


No — one container = one image.
A container is always created from one specific image.
You can't run multiple images inside one container.



| Docker (Containers)     | Virtual Machines            |
| ----------------------- | --------------------------- |
| Lightweight             | Heavy (full OS inside)      |
| Shares host OS kernel   | Has own OS kernel           |
| Fast start (seconds)    | Slow start (minutes)        |
| Uses less resources     | Uses more CPU, RAM, Disk    |
| Ideal for microservices | Ideal for full OS isolation |



Docker Components

Docker Engine — core part that runs containers.

Docker Images — blueprint for containers.

Docker Containers — running instance of an image.

Dockerfile — file containing instructions to build an image.

Docker Hub — public registry for images.

Docker Compose — tool to manage multi-container apps.