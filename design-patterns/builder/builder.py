# The Builder Pattern is a creational design pattern that constructs complex objects step-by-step, separating the construction logic from the final representation. It enables creating different types of objects using the same, flexible process, often replacing "telescoping constructors"

# Step 1: The Product
class HttpRequest:
    def __init__(self, url, method, headers, params, body, timeout, retries, verify_ssl):
        self.url = url
        self.method = method
        self.headers = headers
        self.params = params
        self.body = body
        self.timeout = timeout
        self.retries = retries
        self.verify_ssl = verify_ssl

    def __repr__(self):
        return (
            f"HttpRequest(method={self.method}, url={self.url}, "
            f"timeout={self.timeout}, retries={self.retries})"
        )


# Step 2: The Builder
class HttpRequestBuilder:
    def __init__(self, url):
        self._url = url
        self._method = "GET"
        self._headers = {}
        self._params = None
        self._body = None
        self._timeout = 10
        self._retries = 0
        self._verify_ssl = True
        
    def method(self, method: str):
        self._method = method.upper()
        return self
    
    def headers(self, headers: dict):
        self._headers.update(headers)
        return self
    
    def params(self, params: dict):
        self._params = params
        return self
    
    def body(self, body: dict):
        self._body = body
        return self
    
    def timeout(self, timeout: int):
        if timeout <= 0:
            raise ValueError("Timeout must be positive")
        self._timeout = timeout
        return self
    
    def retries(self, retries: int):
        if retries < 0:
            raise ValueError("Retries cannot be negative")
        self._retries = retries
        return self

    def verify_ssl(self, verify: bool):
        self._verify_ssl = verify
        return self
    
    def build(self) -> HttpRequest:
        if not self._url.startswith("http"):
            raise ValueError("Invalid URL")

        if self._method in {"POST", "PUT"} and self._body is None:
            raise ValueError(f"{self._method} request must have a body")

        return HttpRequest(
            url=self._url,
            method=self._method,
            headers=dict(self._headers),
            params=self._params,
            body=self._body,
            timeout=self._timeout,
            retries=self._retries,
            verify_ssl=self._verify_ssl,
        )


# Step 3: Usage (this is why Builder is loved)
request = (
    HttpRequestBuilder("https://api.service.com/users")
        .method("post")
        .headers({"Authorization": "Bearer token"})
        .body({"name": "vikas"})
        .timeout(5)
        .retries(3)
        .build()
)

print(request)