from __future__ import annotations

from pickle import dumps


class Writable:
    def __init__(self, content: str | list | dict) -> None:
        self._content = content

    @property
    def content(self) -> object:
        return self._content

    @content.setter
    def content(self, value: str | list | dict) -> None:
        self._content = value

    @property
    def dumped(self) -> bytes:
        return dumps(self.content)


class Bitmap(Writable):
    def __init__(self, data: str, offset: int = 0) -> None:
        super().__init__(data)
        self._offset = offset
        self._size = len(self.dumped)

    @property
    def offset(self) -> int:
        return self._offset

    @property
    def size(self) -> int:
        return self._size

    def update(self, value: str, pos: list[int]) -> Bitmap:
        bitmap_array = list(self.content)
        for p in pos:
            bitmap_array[p] = value
        return Bitmap("".join(bitmap_array))


class Inode(Writable):
    def __repr__(self) -> str:
        return "\n".join([f"{k}: {v}" for k, v in self.content.items()])


class Data(Writable):
    def split(self, chunk_size: int) -> list[bytes]:
        arr = self.dumped
        chunks = []
        for i in range(0, len(arr), chunk_size):
            chunks.append(arr[i: i + chunk_size])
        return chunks
