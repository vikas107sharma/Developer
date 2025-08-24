import threading

class Singleton:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:  # Lock for thread safety
            if cls._instance is None:
                print("Singleton Constructor Called!")
                cls._instance = super(Singleton, cls).__new__(cls)
        return cls._instance


# Test
if __name__ == "__main__":
    s1 = Singleton()
    s2 = Singleton()

    print(s1 == s2)  # True
