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



# ----------------------------------------- Class -----------------------------------------
class Student():
    def __init__(self, name, age, score):
        self.name = name               
        self.age = age                  
        self.score = score              
    
    # Provides a user-friendly string representation for print().
    def __str__(self): 
        return f"Name: {self.name}, Age: {self.age}, Score: {self.score}"
    
    # Provides an official, developer-friendly string to recreate the object.
    def __repr__(self): 
        return f"Student(name='{self.name}', age={self.age}, score={self.score})"


student = Student("John", 20, 100) # Create an instance of the Student class.
print(student)   # Calls student.__str__() automatically, printing: Name: John, Age: 20, Score: 100
print(student)   # Calls student.__repr__() automatically, printing: Student(name='John', age=20, score=100)


# 1. @abstractmethod
# Comes from abc (Abstract Base Class) module.
# Used to force subclasses to override a method.
# If a subclass doesn’t implement it, creating an object of that subclass will raise an error.
# If a class has any abstract methods that are not implemented, you cannot instantiate it.

from abc import ABC, abstractmethod

class Shape(ABC):
    @abstractmethod
    def area(self):
        pass

class Circle(Shape):
    def __init__(self, r):
        self.r = r

    def area(self):
        return 3.14 * self.r * self.r

# shape = Shape()  # ❌ Error — abstract method not implemented
circle = Circle(5)
print(circle.area())  # ✅ Works: 78.5


# 2. @staticmethod
# Defines a method inside a class that does not use self or cls.
# Behaves like a normal function but lives in the class namespace.
# Often used for utility/helper methods.

class MathUtils:
    @staticmethod
    def add(a, b):
        return a + b

print(MathUtils.add(3, 4))  # 7


# 3. @classmethod
# Receives cls instead of self as the first parameter.
# Can modify class-level variables.
# Often used as alternative constructors.

class Person:
    species = "Human"

    def __init__(self, name):
        self.name = name

    @classmethod
    def from_full_name(cls, full_name):
        first_name = full_name.split()[0]
        return cls(first_name)

p = Person.from_full_name("John Doe")
print(p.name)       # John
print(p.species)    # Human


# 4. @property
# Turns a method into a read-only attribute.
# Lets you use getter logic without calling it like a function.
# Can be combined with @<property>.setter to make it writable.

class Rectangle:
    def __init__(self, w, h):
        self.w = w
        self.h = h

    @property
    def area(self):
        return self.w * self.h

rect = Rectangle(5, 4)
print(rect.area)  # 20 (no parentheses!)
# rect.area = 30  # ❌ Error — read-only



# ----------------------------------------- Threading -----------------------------------------
import asyncio
# Sum function to take any arguments
def sum(*args):
    return sum(map(lambda x: x, args))

print(sum(1, 2, 3, 4, 5))


# Asynchronous function - non-blocking
async def async_fn():
    await asyncio.sleep(5)

async def async_main():
    await async_fn()

# Synchronous function - blocking
def sync_fn():
    time.sleep(5)

def sync_main():
    sync_fn()  # This blocks the entire thread while sleeping

# Key differences:
# - Async functions allow the event loop to run other tasks while waiting
# - Sync functions block everything until they complete


## Decorators
# @staticmethod: Defines a method bound to a class (not instance/class itself), used for utility functions.
# @classmethod: Binds a method to the class (not instance), with cls as the first argument for factory methods.
# @property: Converts a method into a read-only attribute, enabling getter/setter logic.
# @abstractmethod: Marks a method as abstract (must be overridden in child classes, used with ABC).

## SQLAlchemy Query Methods
# first(): Returns the first row of a query result or None if empty.
# fetchone(): Fetches the next row (DBAPI style), often used with raw SQL.
# one(): Returns exactly one row or raises NoResultFound/MultipleResultsFound.
# all(): Returns all rows as a list (eager load).
# scalar(): Returns the first column of the first row (useful for single-value queries).


# Python supports both single-threaded and multi-threaded execution. However, its threading behavior has important specifics:

# Python can run multiple threads using the threading module. You can create and start many threads that execute concurrently, and they're useful for I/O-bound tasks like file operations and network requests.

# Because of the Global Interpreter Lock (GIL), standard CPython only allows one thread to execute Python bytecode at a time.

# This means Python threads do not execute CPU-bound tasks in true parallel fashion; only one thread is running Python code at any moment. However, threads can run in parallel when waiting on I/O or when using external libraries that release the GIL (like NumPy).

## In this example, tasks run one after another in the main thread:
import time
def task(name):
    for i in range(3):
        print(f"{name} running: {i}")
        time.sleep(1)

task("Task 1")
task("Task 2")

## tasks run in parallel threads (useful for I/O-bound work):
import threading
import time

def task(name):
    for i in range(3):
        print(f"{name} running: {i}")
        time.sleep(1)

t1 = threading.Thread(target=task, args=("Thread 1",))
t2 = threading.Thread(target=task, args=("Thread 2",))

t1.start()
t2.start()

t1.join()
t2.join()


# ------------------------------------------------ Race condition --------------------------------------------------------------------

# An ATM system where the account balance is initially ₹20,000. Two users simultaneously initiate a withdrawal of ₹15,000 each. Using threads, write code to handle this scenario so that race conditions do not occur and the account balance never goes negative.

import threading
import time

balance = 2_000_000
lock = threading.Lock()           # for thread safety

def withdraw(amount):
    global balance
    with lock:                     # With is a context manager, It ensures setup and cleanup happen automatically (like acquiring and releasing locks, opening and closing files).
        # lock.acquire()           alternative of with
        if amount <= balance:
            time.sleep(0.01)
            balance -= amount
            print(f"Withdrawn: {amount}")
        else:
            print("Invalid amount")
        # lock.release()

# two threads withdrawing 500000 each
atm1 = threading.Thread(target=withdraw, args=(1_500_000,)) # args must be a tuple of arguments.
atm2 = threading.Thread(target=withdraw, args=(1_500_000,)) # Without the comma, Python treats (1_500_000) as just 1_500_000 (an int), not a tuple.

atm1.start()  # thread 1 begins running
atm2.start()  # thread 2 begins running

atm1.join()   # main thread waits for atm1 to finish
atm2.join()   # main thread waits for atm2 to finish

# Main thread: the default thread running your script.
# atm1 / atm2: new threads (separate from the main thread).

print(f"Current balance: {balance}")


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
