const express = require('express')

const app = express()

let app_name = process.env.name

app.get('/', (req, res) => {
    res.send(`${app_name} Hello World!`)
})

app.listen(8080, () => {
    console.log(`${app_name} Server is running on port 8080`)
})