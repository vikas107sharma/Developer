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

