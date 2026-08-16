class AppException(Exception):
    """业务异常：统一携带 HTTP 状态码与业务码。"""

    def __init__(self, message: str, status_code: int = 400, code: int | None = None):
        self.message = message
        self.status_code = status_code
        self.code = code if code is not None else status_code
        super().__init__(message)
