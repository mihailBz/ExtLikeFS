from pickle import dumps


class Writable:
    def __init__(self, content):
        self._content = content

    @property
    def content(self):
        return self._content

    @property
    def dumped(self):
        return dumps(self.content)


class Bitmap(Writable):
    def __init__(self, data, offset=0):
        super().__init__(data)
        self._offset = offset
        self._size = len(self.dumped)

    @property
    def offset(self):
        return self._offset

    @property
    def size(self):
        return self._size

    def update(self, value, pos):
        bitmap_array = list(self.content)
        for p in pos:
            bitmap_array[p] = value
        return Bitmap("".join(bitmap_array))


class Inode(Writable):
    pass


class Data(Writable):
    def split(self, chunk_size):
        arr = self.dumped
        chunks = []
        for i in range(0, len(arr), chunk_size):
            chunks.append(arr[i : i + chunk_size])
        return chunks
