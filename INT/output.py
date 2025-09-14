a = 0
b = 5
while a<b:
    try:
        raise Exception("a is less than b")
    except Exception as e:
        print("Error occurred break the code:", e)
        a += 1
        break
    finally:
        print("Continue the process")
        a += 1
        continue

