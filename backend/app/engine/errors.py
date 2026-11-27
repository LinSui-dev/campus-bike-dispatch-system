"""Transport-independent business errors."""


class DomainError(ValueError):
    def __init__(self, code, message, details=None, status=400):
        super().__init__(message)
        self.code, self.message = code, message
        self.details, self.status = details or {}, status

    def dto(self):
        return {"code": self.code, "message": self.message, "details": self.details}
