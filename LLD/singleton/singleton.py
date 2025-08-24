class Singleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            print("Singleton Constructor called")
            cls._instance = super(Singleton, cls).__new__(cls)
        return cls._instance


# Test
if __name__ == "__main__":
    s1 = Singleton()
    s2 = Singleton()

    print(s1 == s2)  # True
