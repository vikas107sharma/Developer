# Race condition 

# An ATM system where the account balance is initially ₹20,000. Two users simultaneously initiate a withdrawal of ₹15,000 each. Using threads, write code to handle this scenario so that race conditions do not occur and the account balance never goes negative.

import threading
import time

balance = 2_000_000
lock = threading.Lock()           # for thread safety

def withdraw(amount):
    global balance
    with lock:                     # With is a context manager, It ensures setup and cleanup happen automatically (like acquiring and releasing locks, opening and closing files).
        # lock.acquire()           alternative of with
        if amount <= balance:
            time.sleep(0.01)
            balance -= amount
            print(f"Withdrawn: {amount}")
        else:
            print("Invalid amount")
        # lock.release()

# two threads withdrawing 500000 each
atm1 = threading.Thread(target=withdraw, args=(1_500_000,)) # args must be a tuple of arguments.
atm2 = threading.Thread(target=withdraw, args=(1_500_000,)) # Without the comma, Python treats (1_500_000) as just 1_500_000 (an int), not a tuple.

atm1.start()  # thread 1 begins running
atm2.start()  # thread 2 begins running

atm1.join()   # main thread waits for atm1 to finish
atm2.join()   # main thread waits for atm2 to finish

# Main thread: the default thread running your script.
# atm1 / atm2: new threads (separate from the main thread).

print(f"Current balance: {balance}")

