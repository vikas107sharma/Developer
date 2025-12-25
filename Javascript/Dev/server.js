const express = require('express')
const test_router = require('./controller');

const app = express();

app.get("/", (req, res)=>{
    res.status(200).json({message: "success"});
})

app.use('/test', test_router);


app.listen(8000, ()=>{
    console.log('Server is running on 8000');
})