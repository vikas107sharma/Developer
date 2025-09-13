Docker commands


If you have this in docker dompose. 
volumes: - .:/app

And this in Dockerfile
WORKDIR /app 

Then no need to rebuild untill you have't changed docker-compose or requirement.txt

docker-compose restart myapp


