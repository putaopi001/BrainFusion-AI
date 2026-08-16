from typing import Any


def success(data: Any = None, message: str = "success") -> dict:
    """统一成功返回格式：{code:200, message, data}。"""
    return {"code": 200, "message": message, "data": data}


def error(message: str, code: int = 500, data: Any = None) -> dict:
    """统一失败返回格式：{code, message, data}。"""
    return {"code": code, "message": message, "data": data}
