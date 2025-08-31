a = list([1, 2, 2, 3])
print(a)  # [1, 2, 2, 3]

b = set([1, 2, 2, 3])
print(b)  # {1, 2, 3}

c = tuple([1, 2, 3])
print(c)  # (1, 2, 3)

d = dict(name="Alice", age=25)
print(d)  # {'name': 'Alice', 'age': 25}



x = [1, 2, 3]
print(type(x))


x = 10
print(isinstance(x, int))     # True
print(isinstance(x, str))     # False


x = 10
print(str(x))    # '10'
print(float(x))  # 10.0


name = "Python"
print(len(name))  # 6
nums = [10, 20, 30]
print(len(nums))  # 3


x = "hello"
print(dir(x))  # Shows all string methods and attributes


text = "hello\nworld"
print(str(text))   # hello
                   # world
print(repr(text))  # 'hello\nworld'



# Sort and reverse
nums = [3, 1, 2]
nums.sort()
print(nums)
nums.reverse()
print(nums)



# enumerate(iterable) – Get index and value while looping
fruits = ['apple', 'banana', 'cherry']
for index, fruit in enumerate(fruits):
    print(index, fruit, fruits[index])
# 0 apple apple
# 1 banana banana
# 2 cherry cherry



# zip(*iterables) – Combine multiple iterables element-wise
names = ['Alice', 'Bob']
scores = [85, 92]
for name, score in zip(names, scores):
    print(name, score)



d = {'a': 1, 'b': 2, 'c': 3}
for key, val in d.items():
    print(key, val)



values = [0, False, 5]
print(any(values))  # True (because 5 is truthy)



flags = [True, 1, "yes"]
print(all(flags))  # True
flags = [True, 0, "yes"]
print(all(flags))  # False (0 is falsy)



# string slicing
# string[start:stop:step]
# start: index to begin (inclusive)
# stop: index to end (exclusive)
# step: how many characters to skip

s = "Python"
print(s[2:5])   # 'tho'  → chars at index 2, 3, 4
print(s[:3])    # 'Pyt'  → from start to index 2
print(s[3:])    # 'hon'  → from index 3 to end
print(s[:])     # 'Python' → whole string
print(s[-1])    # 'n'    → last character
print(s[1::2])  # 'yhn'  → start at 1, skip 2
print(s[::-1])  # 'nohtyP'
print(s[0:100]) # 'Python'



# 📋 List Methods
lst = [1, 2, 3]
lst.append(4)       # Add to end
lst.pop()           # Remove last and return
lst.sort()          # Sort in-place
lst.reverse()       # Reverse in-place
lst.index(3)        # Find index of value
lst.count(1)        # Count occurrences
lst.remove(2)       # Remove the first occurrence of the value 2



# 🔗 Tuple Methods
t = (1, 2, 3, 2)
t.count(2)      # Count how many times 2 occurs
t.index(3)      # Find index of 3



# 🧺 Set Methods
s = {1, 2, 3}
s.add(4)             # Add element
s.discard(5)         # Remove if present (no error)
s.remove(2)          # Remove element (error if not present)
s.pop()              # Remove and return random item
s.clear()            # Empty the set

# Set operations
a = {1, 2, 3}
b = {3, 4, 5}
a.union(b)           # {1, 2, 3, 4, 5}
a.intersection(b)    # {3}
a.difference(b)      # {1, 2}



# 🗃️ Dictionary Methods
d = {'a': 1, 'b': 2}
d.get('a')              # Get value or None
d.keys()                # Get all keys
d.values()              # Get all values
d.items()               # Get (key, value) pairs
d.update({'c': 3})      # Merge another dict
d.pop('b')              # Remove key and return value
d.clear()               # Remove all items



# 🔤 String Methods
s = "hello world"
s.upper()               # 'HELLO WORLD'
s.lower()               # 'hello world'
s.title()               # 'Hello World'
s.strip()               # Remove surrounding whitespace
s.replace("world", "Python")  # Replace substring
s.find("lo")            # Index of first occurrence
s.split()               # ['hello', 'world']
s.join(['a', 'b'])      # 'a b'
s.startswith("he")      # True
s.endswith("ld")        # True