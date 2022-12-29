import re

from typing import Type
from pickle import dumps, loads

from driver import Driver
from bin_serializer import text_from_bits, text_to_bits

Byte = int
Address = int


class OutOfInodes(Exception):
    pass


class FileSystem:
    inode_size: Byte = 256

    def __init__(self, driver: Driver, block_size: Byte, inodes_number: int):

        data_blocks_number = (
                                     driver.device_size - (inodes_number * self.inode_size)
                             ) // block_size
        bitmap_blocks_number = 0

        # 15 bytes - dumped empty string size
        while bitmap_blocks_number * block_size - len(dumps("")) < data_blocks_number:
            bitmap_blocks_number += 1
        data_blocks_number -= bitmap_blocks_number

        self.bitmap = Bitmap("0" * data_blocks_number, offset=0)
        driver.write(self.bitmap.offset, self.bitmap.dumped)

        self._driver = driver
        self._block_size = block_size
        self._inode_sector_offset = self.bitmap.offset + self.bitmap.size + 1
        self._inodes_number = inodes_number
        self._data_sector_offset = (
                self._inode_sector_offset + 1 + self.inode_size * inodes_number
        )

        self._root_directory = self.create_file("/", [".", ".."], Directory)

    def create_file(self, name, data, file_cls):
        data = Data(data)
        data_size = len(data.dumped)

        required_blocks_number = 0
        while required_blocks_number * self._block_size < data_size:
            required_blocks_number += 1

        addresses = self.get_free_blocks(required_blocks_number)

        chunks = data.split(self._block_size)
        assert len(addresses) == len(chunks)
        for data_chunk, addr in zip(chunks, addresses):
            self._driver.write(
                self._data_sector_offset + addr * self._block_size, data_chunk
            )

        self.bitmap = self.bitmap.update("1", addresses)
        self._driver.write(self.bitmap.offset, self.bitmap.dumped)

        inode_id = self.get_free_inode()
        inode = Inode(
            name, file_cls.ftype, file_cls.default_links_cnt, data_size, addresses
        )

        self._driver.write(
            self._inode_sector_offset + inode_id * self.inode_size, inode.dumped
        )

        print(
            f"bitmap: {loads(self._driver.read(self.bitmap.offset, self.bitmap.size))}"
        )
        if file_cls.ftype == 'd':
            print(
                f"rootdir inode: {loads(self._driver.read(self._inode_sector_offset, self.inode_size))}"
            )
            print(
                f"rootdir: {loads(self._driver.read(self._data_sector_offset, self._block_size))}"
            )

        if file_cls.ftype == "f":
            print(
                f"file inode: {loads(self._driver.read(self._inode_sector_offset + 1 * self.inode_size, self.inode_size))}"
            )
            addr = self._data_sector_offset + 1 * self._block_size
            n_bytes = self._block_size
            print(f"file: {loads(self._driver.read(addr, n_bytes))}")

        return file_cls(inode)

    def get_free_blocks(self, n: int) -> list[Address]:
        bitmap = loads(self._driver.read(self.bitmap.offset, self.bitmap.size))
        free_blocks = [m.start() for m in re.finditer("0", bitmap)]
        return free_blocks[:n]

    def get_free_inode(self):
        for i in range(self._inodes_number):
            if (
                    self._driver.read(
                        self._inode_sector_offset + i * self.inode_size, self.inode_size
                    )
                    == b"\x00"
            ):
                return i
        raise OutOfInodes


class Inode:
    def __init__(
            self,
            file_name: str,
            file_type: str,
            links_cnt: int,
            file_size: Byte,
            data_blocks: list[Address],
    ):
        self._attrs = {
            "file_name": file_name,
            "file_type": file_type,
            "links_count": links_cnt,
            "file_size": file_size,
            "data_blocks_map": data_blocks,
        }

    @property
    def dumped(self):
        return dumps(self._attrs)


class Data:
    def __init__(self, data):
        self._data = data
        self._dumped = dumps(data)

    @property
    def data(self):
        return self._data

    @property
    def dumped(self):
        return self._dumped

    def split(self, chunk_size):
        arr = self.dumped
        chunks = []
        for i in range(0, len(arr), chunk_size):
            chunks.append(arr[i: i + chunk_size])
        return chunks


class Bitmap(Data):
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
        bitmap_array = list(self.data)
        for p in pos:
            bitmap_array[p] = value
        return Bitmap("".join(bitmap_array))


class File:
    def __init__(self, inode: Inode):
        self._inode = inode


class Directory(File):
    ftype = "d"
    default_links_cnt = 2


class RegularFile(File):
    ftype = "f"
    default_links_cnt = 1


class Symlink(File):
    ftype = "l"
    default_links_cnt = 1
