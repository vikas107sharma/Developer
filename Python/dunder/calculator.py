# This can be run independently and it can be imported also.

def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

# We don’t always need if __name__ == "__main__":, but we use it to: Prevent code from auto-running when imported.
# If it’s imported → __name__ = "calculator" (the module’s name).
if __name__ == "__main__":
    print("This is a simple calculator!")
    print(f"The sum is: {add(20, 10)}")
    print(f"The difference is: {subtract(20, 10)}")