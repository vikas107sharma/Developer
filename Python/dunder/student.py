class Student():
    def __init__(self, name, age, score):
        self.name = name               
        self.age = age                  
        self.score = score              
    
    # Provides a user-friendly string representation for print().
    def __str__(self): 
        return f"Name: {self.name}, Age: {self.age}, Score: {self.score}"
    
    # Provides an official, developer-friendly string to recreate the object.
    def __repr__(self): 
        return f"Student(name='{self.name}', age={self.age}, score={self.score})"


student = Student("John", 20, 100) # Create an instance of the Student class.
print(student)   # Calls student.__str__() automatically, printing: Name: John, Age: 20, Score: 100
print(student)   # Calls student.__repr__() automatically, printing: Student(name='John', age=20, score=100)
