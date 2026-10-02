from pathlib import Path


class AppError(RuntimeError):
    def __init__(self, code: str, message: str, path: Path | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.path = path
