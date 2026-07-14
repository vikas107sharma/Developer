class Singleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            print("Creating Singleton instance...")
            cls._instance = super().__new__(cls)
        return cls._instance


# Usage
s1 = Singleton()
s2 = Singleton()

print(s1 is s2)  # True
print(id(s1), id(s2))
