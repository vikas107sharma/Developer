# If I run function.py then it inport the calculator module and runs entire code inside it but if we use dunder method __name__ == '__main__' in calculator module then the file will only be imported but does not runs the code.
import calculator    # __name__ == "__main__"

import utils         # without __name__ == "__main__"
import student       # __str__ and __repr__
from connections import mobile, wifi   # __init__.py

mobile.connect_to_mobile()
wifi.connect_to_wifi()

# Define two numbers
num1 = 10
num2 = 5

# Use the functions from the calculator module and print the results
print(f"Using the calculator module:")
print(f"The sum of {num1} and {num2} is: {calculator.add(num1, num2)}")
print(f"The difference between {num1} and {num2} is: {calculator.subtract(num1, num2)}")