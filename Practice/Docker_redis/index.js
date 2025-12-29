import express, { json } from 'express'; //  "type": "module" in package.json 
// or use: const express = require('express')

import { createClient } from 'redis';
import { database } from './db.js';
import { fixed_window_rate_limiter } from './redis.js'; 

// 1. Initialize Client (Use the Service Name from your docker-compose)
const redisClient = createClient({
    // Look for REDIS_URL from Docker/Environment, otherwise use localhost
    url: process.env.REDIS_URL || 'redis://localhost:6379' // Use environment variable or fallback to localhost
});

// 2. Connect to Redis
await redisClient.connect().then(()=>{
  console.log("Connected to Redis");
}).catch((err)=>{
  console.error("Failed to connect to Redis:", err);
})

const app = express();
const PORT = 3000;

app.get('/', (req, res) => {
  res.send('Hello from Dockerized Node!');
});

app.get('/user/:id', fixed_window_rate_limiter(redisClient), async(req, res)=> { // Corrected: Pass redisClient to the middleware
  const {id} = req.params;

  const cachedUser = await redisClient.get(id);

  let user;

  if (cachedUser) {
    console.log("Getting user from redis");
    user = JSON.parse(cachedUser);
  } else {
    console.log("Setting user into redis");
    user = database.users.find(u => u.id === id); // Use strict equality
    if (user) {
        await redisClient.set(id, JSON.stringify(user), { EX: 60 }); // Stringify the user object
    }
  }
  res.status(200).json({success: true, data: user});
});

app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});