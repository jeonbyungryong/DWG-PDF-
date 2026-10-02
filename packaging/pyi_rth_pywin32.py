"""Make pywin32's system DLL directory importable in an onedir bundle."""

import os
import sys


directory = os.path.join(sys._MEIPASS, "pywin32_system32")
_dll_directory_handle = None
if os.path.isdir(directory):
    if directory not in sys.path:
        sys.path.append(directory)
    add_dll_directory = getattr(os, "add_dll_directory", None)
    if add_dll_directory is not None:
        _dll_directory_handle = add_dll_directory(directory)
