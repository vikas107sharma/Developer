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
CMD [ "npm", "start" ]

# To use nodemon 
# put "start": "nodemon index.js" in package.json
# you directly can't write CMD [ "nodemon", "index.js" ]