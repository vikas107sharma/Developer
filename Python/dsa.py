element = dict({"a": 0, "b": 1});

# increament 
element["a"] = element.get("a", 0) + 1


# check and del
if "a" in element:
    del element["a"] # or element.pop("a", None) 
    print(element)

# del removes key and raises KeyError if not exist 
# pop removes key and but can be made safe
