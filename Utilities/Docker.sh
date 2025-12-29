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




----------------------------------------------------------------------------------------------------------------------------------------------------

Docker file

FROM node:18

WORKDIR /app

COPY . ./

RUN npm install

CMD [ "node", "index.js" ]


----------------------------------------------------------------------------------------------------------------------------------------------------

Docker file optimized

FROM node:18-alpine

# WORKDIR /app is like typing cd /app
WORKDIR /app

# The "./" refers to the current WORKDIR (/app)
COPY package.json ./
COPY package-lock.json ./

# Install dependencies inside /app
# Copy packages and install it first for layered caching so that whenever your code changes and you rebuild the image these are directly used from cache (previous layers)
# But where there is any change in package.json then it will run again
# Docker layer caching is a mechanism that reuses the results of previous builds to accelerate the creation of Docker images. Each instruction in a Dockerfile (such as RUN, COPY, or ADD) creates a unique layer. If the instruction and its input files remain unchanged, Docker reuses the existing layer from the cache instead of rebuilding it. 
RUN npm install

# Copy all other files from your computer into /app
# COPY . . looks like: "Copy everything here to there."
# COPY . ./ looks like: "Copy everything here into the current folder." (./) is considered a "best practice"
COPY . ./

# Inform users/tools that we listen on 3000. (The EXPOSE instruction is primarily documentation. It tells whoever is using your Docker image: "Hey, the application inside this container is designed to listen on Port 3000.")
# The -P trick: If you use a capital -P when running your container (docker run -P), Docker will automatically take all ports listed in EXPOSE and map them to random high-number ports on your host.
# If you have 5 different Node apps all trying to use Port 3000, they will crash if you try to map them all to -p 3000:3000. Using -P lets Docker handle the traffic control for you.
# The -P flag only works if you have the EXPOSE 3000 line in your Dockerfile. If you remove that line, -P will do nothing because Docker won't know which internal ports are available to be mapped.
EXPOSE 3000 

# Run index.js (which is now at /app/index.js)
CMD [ "node", "index.js" ]


----------------------------------------------------------------------------------------------------------------------------------------------------

# Single stage image size was: 129.88 MB
# now it is: 129.05 MB

# --- STAGE 1: Build Stage ---
FROM node:18-alpine AS builder
WORKDIR /build

# Copy only what we need for installing dependencies
COPY package*.json ./
RUN npm install

# Copy everything else and build (if you had a build step)
COPY . .

# --- STAGE 2: Run Stage ---
FROM node:18-alpine AS runner
WORKDIR /app

# IMPORTANT: We only copy the necessary files from the "builder" stage
COPY --from=builder /build/package.json ./
COPY --from=builder /build/node_modules ./node_modules  # when you wrote: COPY --from=builder /build/node_modules ./ The Problem: In Docker, when you copy a folder to ./, it copies the contents of that folder, not the folder itself, due to which files are scattered in /app
COPY --from=builder /build/index.js ./

EXPOSE 3000

# Start the app
CMD ["node", "index.js"]

----------------------------------------------------------------------------------------------------------------------------------------------------


Docker compose


version: '3.8'

# docker build -f .\Dockerfile -t app .
# docker run -p 3000:3000 app 
services:
  app:
    build: .
    ports:
      - "3000:3000"
    volumes:
      - .:/app  # This is a key-value pair for file syncing. It follows the format: [Source on your PC] : [Destination in Container]
      - /app/node_modules # Your local node_modules was built for your host OS (likely Windows), but the container runs Linux Alpine # Prevent overwriting container's node_modules


----------------------------------------------------------------------------------------------------------------------------------------------------