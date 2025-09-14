class HardwareError(Exception):
    """Custom exception for hardware-related errors."""
    def __init__(self, message="A hardware error occurred.", value=None):
        self.message = message   # set first
        self.value = value
        super().__init__(self.message)  # now call parent

    def __str__(self):
        return f"message: {self.message} | value: {self.value}"


try:
    temp = 200
    if temp > 100:
        raise HardwareError("System is overheating", temp)
except HardwareError as e:
    print("Error:", e)


