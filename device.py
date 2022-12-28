from os.path import exists

Byte = int


class InvalidSize(Exception):
    pass


class StorageDevice:
    def __init__(self, size: Byte, path: str, clear=False):
        self._size = size
        self._path = path
        if exists(path) and not clear:
            with open(path, 'r') as f:
                if len(f.read()) / 8 != size:
                    raise InvalidSize
        else:
            with open(path, 'w') as f:
                f.write('0' * size * 8)

    @property
    def size(self):
        return self._size

    @property
    def path(self):
        return self._path
