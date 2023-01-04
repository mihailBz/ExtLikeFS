from os.path import exists

from fs_exceptions import *

Byte = int


class StorageDevice:
    def __init__(self, size: Byte, path: str, use_existing: bool = False) -> None:
        self._size = size
        self._path = path
        if exists(path) and use_existing:
            with open(path, "r") as f:
                if len(f.read()) / 8 != size:
                    raise InvalidSize
        else:
            with open(path, "w") as f:
                f.write("0" * size * 8)

    @property
    def size(self) -> Byte:
        return self._size

    @property
    def path(self) -> str:
        return self._path
