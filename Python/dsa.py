arr = [1,2,3,4,5]
element = dict({"a": 0, "b": 1});

# increament 
element["a"] = element.get("a", 0) + 1

# check and del
if "a" in element:
    element.pop("a", None) # del element["a"]
    print(element)

# del removes key and raises KeyError if not exist 
# pop removes key and but can be made safe

# Iterate over dictionary (key-value pairs)
for key, val in element.items():
    pass

# Iterate over list/array (index-value pairs)
for idx, val in enumerate(arr):
    pass

