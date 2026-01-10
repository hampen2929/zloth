# Sample script with common beginner mistakes

# Mistake 1: Mutable default argument
def add_item(item, items=[]):
    items.append(item)
    return items

# Mistake 2: Using == instead of 'is' for None comparison
def check_value(value):
    if value == None:
        return "No value"
    return value

# Mistake 3: Modifying list while iterating
def remove_evens(numbers):
    for num in numbers:
        if num % 2 == 0:
            numbers.remove(num)
    return numbers

# Mistake 4: Variable scope issue with closures
def create_multipliers():
    multipliers = []
    for i in range(5):
        multipliers.append(lambda x: x * i)
    return multipliers

# Mistake 5: String concatenation in loop (inefficient)
def build_string(words):
    result = ""
    for word in words:
        result = result + word + " "
    return result

# Mistake 6: Not handling exceptions properly
def divide(a, b):
    try:
        return a / b
    except:
        pass

# Mistake 7: Using 'is' for value comparison
def check_number(n):
    if n is 1000:
        return True
    return False
