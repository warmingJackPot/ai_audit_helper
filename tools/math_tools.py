"""math_tools"""
from mcp_registry import mcp

# @mcp.tool(name="add_numbers",
#           host="vm1",
#           args=['a', 'b'],
#           description="Складывает два числа, используй для простых арифметических выражений")

# def add_numbers(a: float, b: float) -> float:
#     """Складывает два числа и возвращает результат"""
#     res = float(a) + float(b)

#     return res


@mcp.tool(
    name="calculate_numbers",
    host="vm1",
    args=['a', 'b', 'operation'],
    description="Выполняет арифметическую операцию (sum, difference, multiply, divide) над двумя числами."
)
def calculate_numbers(a: float, b: float, operation: str) -> float:
    """
    Выполняет арифметическую операцию над двумя числами.
    Поддерживаемые операции: sum, multiply, divide.
    """
    a, b = float(a), float(b)

    if operation == "sum":
        res = a + b
    elif operation == "difference":
        res = a - b 
    elif operation == "multiply":
        res = a * b
    elif operation == "divide":
        if b == 0:
            raise ValueError("Деление на ноль запрещено.")
        res = a / b
    else:
        raise ValueError(f"Неизвестная операция: {operation}")

    return res
