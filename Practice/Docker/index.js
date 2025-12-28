import express from 'express'; //  "type": "module" in package.json 
// or use: const express = require('express')

const app = express();
const PORT = 3000;

app.get('/', (req, res) => {
  res.send('Hello from Dockerized Node!');
});

app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});