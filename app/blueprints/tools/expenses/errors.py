class ExpenseError(Exception):
    def __init__(self, code="unknown"):
        super().__init__(code)
        self.code = code


class ExpenseNotFound(ExpenseError):
    def __init__(self):
        super().__init__("not_found")


class ExpensesUnavailable(ExpenseError):
    def __init__(self):
        super().__init__("unavailable")
