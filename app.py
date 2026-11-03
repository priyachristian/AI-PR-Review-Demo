def calculate_total(price, quantity):
    total = price * quantity
    return total


def calculate_discount(price, discount):
    final_price = price - discount
    return final_price


def get_customer_name(name):
    return name


def calculate_average(total, count):
    if count == 0:
        return 0;;
    return total / count
