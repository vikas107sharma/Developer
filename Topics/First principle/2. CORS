
CORS (Cross-Origin Resource Sharing) is a browser-enforced security mechanism that restricts a web page from making requests to a different domain (origin) than the one that served it. It relaxes the strict Same-Origin Policy by allowing backend servers to explicitly whitelist specific origins via the Access-Control-Allow-Origin header.

(Scheme + Host + PORT)       -> If any one is different then it is different origin
https + piyushgarg.dev + 443

Different origin (port is different)
localhost:5173
localhost:8000


======================== CORS (Code level) ========================

OPTION 1
cors package is the safest and most standard way to manage origins in production. It handles preflight requests (OPTIONS), header validation, and edge cases automatically.

const express = require('express');
const cors = require('cors');

const app = express();

const corsOptions = {
    // Specify the allowed origin
    origin: 'https://example.com',
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization'],
    credentials: true, // Necessary if you are sending cookies or authorization headers
    optionsSuccessStatus: 204
};

// Apply globally to all routes
app.use(cors(corsOptions));

app.get('/api/test', (req, res) => {
    return res.status(200).json({ status: 'success' });
});

app.listen(3000);


// OPTION 2
const express = require('express');
const app = express();

app.use((req, res, next) => {
    res.setHeader('Access-Control-Allow-Origin', 'https://example.com');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
    res.setHeader('Access-Control-Allow-Credentials', 'true');

    // Intercept preflight requests
    if (req.method === 'OPTIONS') {
        return res.sendStatus(204);
    }

    next();
});

app.get('/api/test', (req, res) => {
    return res.status(200).json({ status: 'success' });
});

app.listen(3000);

 



======================== CORS (Reverse proxy) ========================

server {
    listen 80;
    server_name api.example.com;

    location / {
        # Catch preflight OPTIONS requests and return 204 immediately
        if ($request_method = 'OPTIONS') {
            add_header 'Access-Control-Allow-Origin' 'https://example.com' always;
            add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
            add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Authorization' always;
            add_header 'Access-Control-Max-Age' 1728000 always;
            add_header 'Content-Type' 'text/plain; charset=utf-8';
            add_header 'Content-Length' 0;
            return 204;
        }

        # Apply standard CORS headers to regular requests
        add_header 'Access-Control-Allow-Origin' 'https://example.com' always;
        add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
        add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Authorization' always;

        # Proxy to your Node.js application
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}