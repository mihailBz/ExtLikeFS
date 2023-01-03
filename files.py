from __future__ import annotations

from writable import Inode, Data

Byte = int


class File:
    ftype = None
    default_links_cnt = None

    def __init__(self, inode: Inode, data: Data) -> None:
        self._inode = inode
        self._data = data

    @property
    def data(self) -> Data:
        return self._data

    @data.setter
    def data(self, value: Data) -> None:
        self._data = value

    @property
    def inode(self) -> Inode:
        return self._inode


class Directory(File):
    ftype = "d"
    default_links_cnt = 2

    def __repr__(self) -> str:
        return "\n".join([f"{v} {k}" for k, v in self.data.content.items()])


class RegularFile(File):
    ftype = "f"
    default_links_cnt = 1

    def __init__(self, inode: Inode, data: Data, seek_pos: int = 0) -> None:
        self._seek_pos = seek_pos
        super().__init__(inode, data)

    @property
    def seek(self) -> int:
        return self._seek_pos

    @seek.setter
    def seek(self, value: int) -> None:
        self._seek_pos = value

    def read(self, size: Byte) -> bytes:
        data = self.data.content.encode()
        start = self.seek if self.seek == 0 else self.seek - 1
        end = start + size
        self.seek = end
        if end > len(data):
            self.seek = len(data)
            return data[start:]
        else:
            return data[start:end]

    def write(self, data: bytes, size: Byte) -> RegularFile:
        if self.data is None:
            self.data = Data((b"\x00" * self.seek + data[:size]).decode())
        elif len(self.data.content.encode()) < self.seek:
            gap_size = len(self.data.content.encode()) - self.seek
            self.data.content = (
                self.data.content.encode() + b"\x00" * gap_size + data[:size]
            ).decode()
        else:
            self.data.content = (
                self.data.content.encode()[: self.seek] + data[:size]
            ).decode()
        self.seek += size
        return RegularFile(self.inode, self.data, self.seek)


class Symlink(File):
    ftype = "l"
    default_links_cnt = 1
