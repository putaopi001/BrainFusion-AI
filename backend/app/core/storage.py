"""One configurable uploads namespace; preserve explicitly stored legacy paths."""
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
from app.core.config import settings

BACKEND = Path(__file__).resolve().parents[2]


def upload_root():
    return Path(settings.UPLOAD_DIR).resolve()


def is_supported_storage_path(value, platform=None):
    """Keep Windows runtime data on E:, while allowing absolute container paths."""
    runtime = os.name if platform is None else platform
    if runtime == 'nt':
        path = PureWindowsPath(str(value))
        if not path.is_absolute():
            return False
        return path.drive.upper() == 'E:'
    return PurePosixPath(str(value)).is_absolute()


def resolve_stored_path(value):
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    parts = path.parts
    if parts and parts[0].lower() == 'uploads':
        return (upload_root() / Path(*parts[1:])).resolve()
    return (BACKEND / path).resolve()


def public_upload_path(value):
    if not value:
        return None
    try:
        relative = resolve_stored_path(value).relative_to(upload_root())
    except (ValueError, OSError):
        return None
    return '/uploads/' + relative.as_posix()
