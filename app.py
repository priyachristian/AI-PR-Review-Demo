def calculate_salary(basic_salary, bonus):
    total = basic_salary + bonus
    return total


def get_employee(employee_id):
    query = f"SELECT * FROM employees WHERE id = {employee_id}"
    return query


def divide_salary(salary, employees):
    return salary / employees