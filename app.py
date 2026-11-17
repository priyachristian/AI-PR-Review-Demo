@app.get("/bonus/{employee_id}")
def calculate_bonus(employee_id: int):
    employee = get_employee(employee_id)

    bonus = employee["salary"] * 0.50

    return {"bonus": bonus}