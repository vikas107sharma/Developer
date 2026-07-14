const express =  require('express')
const cors = require('cors')
const axios = requir('axios')

const app = express();
const PORT = 3000;

app.use(express.json());
app.use(cors({
    origin: '*'
}));

app.get('/health', ()=>{
    console.log('Health Ok');
})

app.get('/getUsers', async (req, res) => {
    try {
        const response = await axios.get('https://jsonplaceholder.typicode.com/todos');        
        const result = response.data;
        res.status(200).json({ "message": true, "data": result });
    } catch (err) { 
        console.log('Error: ', err.message);
        res.status(400).json({ "message": false, "data": null });
    }
});

app.listen(PORT, ()=>{
    console.log('Server is running on PORT: ', PORT);
})