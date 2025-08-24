from abc import ABC, abstractmethod


# --- Product Abstract Class ---
class Burger(ABC):
    @abstractmethod
    def prepare(self):
        pass


# --- Concrete Products ---
class BasicBurger(Burger):
    def prepare(self):
        print("Preparing Basic Burger with bun, patty, and ketchup!")


class StandardBurger(Burger):
    def prepare(self):
        print("Preparing Standard Burger with bun, patty, cheese, and lettuce!")


class PremiumBurger(Burger):
    def prepare(self):
        print("Preparing Premium Burger with gourmet bun, premium patty, cheese, lettuce, and secret sauce!")


class BasicWheatBurger(Burger):
    def prepare(self):
        print("Preparing Basic Wheat Burger with bun, patty, and ketchup!")


class StandardWheatBurger(Burger):
    def prepare(self):
        print("Preparing Standard Wheat Burger with bun, patty, cheese, and lettuce!")


class PremiumWheatBurger(Burger):
    def prepare(self):
        print("Preparing Premium Wheat Burger with gourmet bun, premium patty, cheese, lettuce, and secret sauce!")


# --- Factory Abstract Class ---
class BurgerFactory(ABC):
    @abstractmethod
    def create_burger(self, type_: str) -> Burger:
        pass


# --- Concrete Factories ---
class SinghBurger(BurgerFactory):
    def create_burger(self, type_: str) -> Burger:
        if type_ == "basic":
            return BasicBurger()
        elif type_ == "standard":
            return StandardBurger()
        elif type_ == "premium":
            return PremiumBurger()
        else:
            print("Invalid burger type!")
            return None


class KingBurger(BurgerFactory):
    def create_burger(self, type_: str) -> Burger:
        if type_ == "basic":
            return BasicWheatBurger()
        elif type_ == "standard":
            return StandardWheatBurger()
        elif type_ == "premium":
            return PremiumWheatBurger()
        else:
            print("Invalid burger type!")
            return None


# --- Client Code ---
if __name__ == "__main__":
    burger_type = "basic"

    # Choose a factory
    my_factory = SinghBurger()

    # Create burger
    burger = my_factory.create_burger(burger_type)

    if burger:
        burger.prepare()
