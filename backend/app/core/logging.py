import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """初始化统一日志格式，并降低第三方库噪声。"""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        stream=sys.stdout,
    )
    for noisy in ("uvicorn.access", "PIL.PngImagePlugin", "matplotlib", "httpx", "h11"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
