from abc import ABC, abstractmethod
from enum import Enum

# TRANSPORT MODES
class TransportMode(Enum):
    BUS = "bus"
    TRAIN = "train"
    FLIGHT = "flight"
    Car = "bike"

class Transportation(ABC):
    @abstractmethod
    def journey(self):
        """Abstract method for transportation journey"""
        pass

class BusTransport(Transportation):
    def journey(self):
        print("Commencing bus journey on road routes")

class TrainTransport(Transportation):
    def journey(self):
        print("Commencing train journey on railway tracks")

class FlightTransport(Transportation):
    def journey(self):
        print("Commencing flight journey through airways")


# TRANSPORT FACTORY
class TransportFactory:
    @abstractmethod
    def create_transport(mode):
        """Factory method to create transportation instances"""
        pass

class DomesticTravelAgency(TransportFactory):
    """Domestic travel agency for local transport"""
    @staticmethod
    def book_transport(mode):
        if mode == TransportMode.BUS.value:
            return BusTransport()
        elif mode == TransportMode.TRAIN.value:
            return TrainTransport()
        elif mode == TransportMode.Car.value:
            return FlightTransport()
        else:
            raise ValueError(f"Unavailable transport mode: {mode}")

class InternationalTravelAgency(TransportFactory):
    """International travel agency for global transport"""
    @staticmethod
    def book_transport(mode):
        if mode == TransportMode.BUS.value:
            return BusTransport()
        elif mode == TransportMode.TRAIN.value:
            return TrainTransport()
        elif mode == TransportMode.FLIGHT.value:
            return FlightTransport()
        else:
            raise ValueError(f"Unavailable transport mode: {mode}")


# USE CASES
def main():
    """Main function to demonstrate transport booking"""
    # Book domestic train transport
    print("\n--- Domestic train trip ---")
    train_trip = DomesticTravelAgency.book_transport("train")
    print(f"Transport booked: {train_trip.__class__.__name__}")
    train_trip.journey()
    
    # Book international flight
    print("\n--- International flight ---")
    international_flight = InternationalTravelAgency.book_transport("flight")
    print(f"Transport booked: {international_flight.__class__.__name__}")
    international_flight.journey()
    
if __name__ == "__main__":
    main()
    
    
    
    
    
    
    
    
    
    
    
# The Factory Design Pattern is a creational pattern that provides an interface for creating objects in a superclass but allows subclasses to alter the type of objects that will be created

# Definition Breakdown:
# 1. "The Factory Design Pattern is a creational pattern..."
# This is a CREATIONAL pattern because it deals with OBJECT CREATION
# Instead of directly creating objects with: BusTransport()
# We use: DomesticTravelAgency.book_transport("bus")

# 2. "...that provides an interface for creating objects in a superclass..."
class TransportFactory:  # <- This is the SUPERCLASS/INTERFACE
    @abstractmethod
    def create_transport(mode):  # <- This is the INTERFACE for creating objects
        pass

# 3. "...but allows subclasses to alter the type of objects that will be created"
class DomesticTravelAgency(TransportFactory):  # <- SUBCLASS 1
    @staticmethod
    def book_transport(mode):
        if mode == TransportMode.BUS.value:
            return BusTransport()  # Creates BusTransport object
        # ... other conditions

class InternationalTravelAgency(TransportFactory):  # <- SUBCLASS 2  
    @staticmethod
    def book_transport(mode):
        if mode == TransportMode.FLIGHT.value:
            return FlightTransport()  # Creates FlightTransport object
        # ... other conditions