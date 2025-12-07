# ----------------------------------------- Immutability -----------------------------------------
# Immutable = the object itself cannot be modified.
# But the variable name can point to a new object.
# you do +=, you’re not mutating the object — you’re creating a new one and reassigning the variable.
text = "hello"
text += "world"   # String is immutable
print(text)  

coordinates = (1,4)
coordinates += (5,)    # Tuple is immutable
print(coordinates)



# ----------------------------------------- Not implemented -----------------------------------------
def get_user():
    pass 

def get_book():
    ...

def get_card():
    raise NotImplementedError("Feature will be live soon")


# ----------------------------------------- CLOSURE -------------------------------------------
import time
import uuid

def connect_DB():
    connection_string = "PostgresDB"  # ENV
    print(f"Setting up connection to {connection_string}")
    time.sleep(2)
    print(f"Connected to {connection_string}")

    def connection():
        session_id = str(uuid.uuid4())[:6]  # generate new session each call
        return f"New Session-{session_id} on {connection_string}"
    
    return connection


# One DB connection, multiple sessions
session = connect_DB()

print(session())  # New Session-<uuid1> on PostgresDB
print(session())  # New Session-<uuid2> on PostgresDB
print(session())  # New Session-<uuid3> on PostgresDB



# ----------------------------------------- API -----------------------------------------

from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/api/data/<path:resource>', methods=['POST'])
def handle_all(resource):
    
    # Extract headers
    headers = {
        'user_agent': request.headers.get('User-Agent'),
        'content_type': request.headers.get('Content-Type')
    }
    # Get all headers as dictionary
    all_headers = dict(request.headers)
    
    # Extract query params
    query = request.args.get('q')
    # Extract all query params
    query_params = request.args.to_dict()
    
    # Extract body data
    # 📥 json() or get_json(): Reading Data INTO Python
    # response.json()	requests	Client-side. Used to decode the JSON response received from a server.
    # request.get_json()	Flask/Werkzeug	Server-side. Used to decode the JSON payload received by the server. 
    body_data = request.get_json()
    
    # Extract form data
    form_data = request.form.to_dict()
    
    return jsonify({
        'method': request.method,
        'resource': resource,
        'headers': headers,
        'query_params': query_params,
        'body_data': body_data,
        'form_data': form_data
    }), 200


if __name__ == '__main__':
    app.run(debug=True)



# ----------------------------------------- API Call -----------------------------------------
import requests
import os
from dotenv import load_dotenv

load_dotenv()

base_url = os.getenv('BASE_URL')
url = f"{base_url}/post"
payload = {
    "name": "Vikas",
    "age": 22
}
headers = {
    "User-Agent": "my-app/1.0",
    "Accept": "application/json"
}

try:
    response = requests.post(url, json=payload, headers=headers, timeout=5)
    print("Status Code:", response.status_code)
    try:
        print(response.json())
    except requests.exceptions.JSONDecodeError:
        print("Response is not in JSON format:")
        print(response.text)
except requests.exceptions.RequestException as e:
    print("Request failed:", e)


# requests.get(url) – Read/fetch data
# requests.post(url, data/json) – Submit data
# requests.put() / patch() – Update data
# requests.delete() – Delete resource
 


# ----------------------------------------- list -----------------------------------------
# Looping on list: enumerate(iterable) – Get index and value while looping
fruits = ['apple', 'banana', 'cherry']
for index, fruit in enumerate(fruits):
    print(index, fruit, fruits[index])
# 0 apple apple
# 1 banana banana
# 2 cherry cherry




# ----------------------------------------- dict -----------------------------------------
# Dic
# Without defaultdict (using a regular dict):
# You have to manually check if the key (the word) exists before you can increment its count.
counts = {}  # or dict()
for word in ['apple', 'banana', 'apple', 'orange', 'banana', 'apple']:
    if word not in counts:
        counts[word] = 0  # Manually initialize the count to 0
    counts[word] += 1
# counts is {'apple': 3, 'banana': 2, 'orange': 1}


# .get() is a very common pattern in Python when you don't want to import defaultdict or when you want to use a standard dictionary.
counts = {} # Standard dictionary
words = ['apple', 'banana', 'apple', 'orange', 'banana', 'apple']

for word in words:
    # counts.get(word, 0) looks for 'word'. 
    # If found, it returns the value. If not found, it returns 0.
    counts[word] = counts.get(word, 0) + 1

print(counts)
# Output: {'apple': 3, 'banana': 2, 'orange': 1}


# DefaultDict
# In a regular dictionary, if you try to access or modify a key that doesn't exist, Python raises a KeyError. defaultdict prevents this by automatically creating a value for the missing key on the spot.
from collections import defaultdict
counts = defaultdict(int)
for word in ['apple', 'banana', 'apple', 'orange', 'banana', 'apple']:
    # If 'apple' is seen for the first time, defaultdict automatically creates
    # the entry counts['apple'] = 0 before the += 1 is executed.
    counts[word] += 1
# counts is defaultdict(<class 'int'>, {'apple': 3, 'banana': 2, 'orange': 1})

# What is the value inside the parentheses?
# The argument you pass to defaultdict is called the default_factory. It must be a callable (like a function or a class) that takes no arguments and returns the default value you want for new keys.
# defaultdict(int) The factory is the int class. When called as int(), it returns 0. This is perfect for counting, as seen in your example.
# defaultdict(list) The factory is the list class. When called as list(), it returns an empty list []. This is extremely useful for grouping items.
from collections import defaultdict
students_by_grade = defaultdict(list)
students_by_grade['one'].append('Alice')
students_by_grade['two'].append('Bob')
students_by_grade['one'].append('Charlie')
# print(students_by_grade)
# defaultdict(<class 'list'>, {'one': ['Alice', 'Charlie'], 'two': ['Bob']})



# Looping on objects
students = {'id_A': 'Alice', 'id_B': 'Bob', 'id_C': 'Charlie'}

# for k in my_dict:	Just the keys	k will be 'id_A', then 'id_B', etc.
for key in students:
    # You can use the key to access the value
    name = students[key]
    print(f"Key: {key}, Value: {name}")

# for k, v in my_dict.items():	Both the key and value	k, v will be ('id_A', 'Alice'), etc.
for key, val in students.items():
    print(key, val)

# for v in my_dict.values():	Just the values	v will be 'Alice', then 'Bob', etc.
for val in students.values():
    print(val)



# ----------------------------------------- lambda -----------------------------------------




# ----------------------------------------- UNDERSCORE -----------------------------------------
# For readability in numbers
big_int = 1_000_000
print(big_int)   # 1000000

# Ignoring a value during unpacking
employee = ("John", "Programmer", 27)
name, _, age = employee             

# Using underscore in loops (when the variable is not used)
for _ in range(5):                 
    print("Hello")




# ----------------------------------------- finally -----------------------------------------
# Example showing why finally is useful
# Case 1: Using finally
try:
    raise ValueError("Bad value")
except ValueError:
    print("Handling value error")
    raise
finally:
    print("DB connection closed.")  # Always executes, even if exception is re-raised


# Case 2: Without finally
try:
    raise ValueError("Bad value")
except ValueError:
    print("Handling value error")
    raise

# This line will never execute because the exception is re-raised
print("DB connection closed.")  
