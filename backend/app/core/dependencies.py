"""Fail before application database initialization when a core dependency is absent."""
import importlib


def require_dicom_parser():
    try:
        return importlib.import_module('pydicom')
    except ModuleNotFoundError as error:
        if error.name != 'pydicom':
            raise
        raise RuntimeError(
            'Required dependency pydicom is missing. Use the supported environment '
            'or install backend/requirements-core.txt into a separate candidate '
            'environment; the application has not initialized its database.'
        ) from error
