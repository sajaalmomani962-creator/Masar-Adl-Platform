class AppError(Exception):
    status = 400
    def __init__(self, message="طلب غير صالح"):
        super().__init__(message)
        self.message = message

class NotFound(AppError):
    status = 404
    def __init__(self, message="غير موجود"):
        super().__init__(message)

class Forbidden(AppError):
    status = 403
    def __init__(self, message="غير مصرّح لك بهذا الإجراء"):
        super().__init__(message)

class NeedsApproval(Forbidden):
    def __init__(self, message="هذا الإجراء يتطلب قرارًا من القاضي المخوّل"):
        super().__init__(message)

class BadRequest(AppError):
    status = 400
