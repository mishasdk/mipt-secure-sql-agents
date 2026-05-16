import logging
import sys

# Глушим логи "app.*" до вызова setup_logging().
# Без этого логи уходят в root logger, который может быть уже настроен uvicorn/langchain/etc.
_app_logger = logging.getLogger("app")
_app_logger.addHandler(logging.NullHandler())
_app_logger.propagate = False


def setup_logging(level: int = logging.INFO, configure_uvicorn: bool = False) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    app_logger = logging.getLogger("app")
    app_logger.handlers.clear()  # убираем NullHandler
    app_logger.setLevel(level)
    app_logger.addHandler(handler)
    app_logger.propagate = False

    if configure_uvicorn:
        for name in ("uvicorn.error", "uvicorn"):
            uv = logging.getLogger(name)
            uv.handlers = [handler]
            uv.setLevel(level)
            uv.propagate = False

        logging.getLogger("uvicorn.access").disabled = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
