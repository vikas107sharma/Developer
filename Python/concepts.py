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
