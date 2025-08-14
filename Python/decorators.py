# 1. @abstractmethod
# Comes from abc (Abstract Base Class) module.
# Used to force subclasses to override a method.
# If a subclass doesn’t implement it, creating an object of that subclass will raise an error.
# If a class has any abstract methods that are not implemented, you cannot instantiate it.

from abc import ABC, abstractmethod

class Shape(ABC):
    @abstractmethod
    def area(self):
        pass

class Circle(Shape):
    def __init__(self, r):
        self.r = r

    def area(self):
        return 3.14 * self.r * self.r

# shape = Shape()  # ❌ Error — abstract method not implemented
circle = Circle(5)
print(circle.area())  # ✅ Works: 78.5


# 2. @staticmethod
# Defines a method inside a class that does not use self or cls.
# Behaves like a normal function but lives in the class namespace.
# Often used for utility/helper methods.

class MathUtils:
    @staticmethod
    def add(a, b):
        return a + b

print(MathUtils.add(3, 4))  # 7


# 3. @classmethod
# Receives cls instead of self as the first parameter.
# Can modify class-level variables.
# Often used as alternative constructors.

class Person:
    species = "Human"

    def __init__(self, name):
        self.name = name

    @classmethod
    def from_full_name(cls, full_name):
        first_name = full_name.split()[0]
        return cls(first_name)

p = Person.from_full_name("John Doe")
print(p.name)       # John
print(p.species)    # Human


# 4. @property
# Turns a method into a read-only attribute.
# Lets you use getter logic without calling it like a function.
# Can be combined with @<property>.setter to make it writable.

class Rectangle:
    def __init__(self, w, h):
        self.w = w
        self.h = h

    @property
    def area(self):
        return self.w * self.h

rect = Rectangle(5, 4)
print(rect.area)  # 20 (no parentheses!)
# rect.area = 30  # ❌ Error — read-only
