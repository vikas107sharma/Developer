import express, { json } from 'express'; //  "type": "module" in package.json 
// or use: const express = require('express')

import { database } from './db.js';
import { redisClient } from './redis.js';
import { fixed_window_rate_limiter } from './redis.js'; 

const app = express();
const PORT = 3000;

app.get('/', (req, res) => {
  res.send('Hello from Dockerized Node!');
});

app.get('/user/:id', fixed_window_rate_limiter(), async(req, res)=> {
  const {id} = req.params;

  const cachedUser = await redisClient.get(id);

  let user;

  if (cachedUser) {
    console.log("Getting user from redis");
    user = JSON.parse(cachedUser);
    // Return early if user is found in cache
    return res.status(200).json({success: true, data: user});
  } else {
    console.log("Setting user into redis");
    user = database.users.find(u => u.id === id); // Use strict equality
    if (user) {
        await redisClient.set(id, JSON.stringify(user), { EX: 60 }); // Stringify the user object
        // Return early after setting in Redis
        return res.status(200).json({success: true, data: user});
    } else {
        // If user is not found in the database
        return res.status(404).json({ success: false, message: "User not found" });
    }
  }
});

app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});