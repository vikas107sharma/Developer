from abc import ABC, abstractmethod

class PaymentStrategy(ABC):
    @abstractmethod
    def pay(self, amount):
        pass


class CreditCardPayment(PaymentStrategy):
    def pay(self, amount):
        print(f"card payment of {amount}")


class UPIPayment(PaymentStrategy):
    def pay(self, amount):
        print(f"upi payment of {amount}")


class CryptoPayment(PaymentStrategy):
    def pay(self, amount):
        print(f"crypto payment of {amount}")


class PaymentProcessor:
    def __init__(self, strategy: PaymentStrategy):
        self._strategy = strategy

    def set_strategy(self, strategy: PaymentStrategy): # To change it after class initialization
        self._strategy = strategy

    def process_payment(self, amount):
        self._strategy.pay(amount)


payment_processor = PaymentProcessor(UPIPayment())
payment_processor.process_payment(10)

payment_processor.set_strategy(CreditCardPayment())
payment_processor.process_payment(20)
