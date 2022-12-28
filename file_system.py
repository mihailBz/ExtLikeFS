import re

from typing import Type
from pickle import dumps, loads

from driver import Driver
from bin_serializer import text_from_bits, text_to_bits

Byte = int
Address = int


class FileSystem:
    inode_size: Byte = 256

    def __init__(self, driver: Driver, block_size: Byte, inodes_number: int):

        data_blocks_number = (driver.device_size - (inodes_number * self.inode_size)) // block_size
        bitmap_blocks_number = 0

        # 15 bytes - dumped empty string size
        while bitmap_blocks_number * block_size - len(dumps('')) < data_blocks_number:
            bitmap_blocks_number += 1
        data_blocks_number -= bitmap_blocks_number

        self.bitmap = Bitmap('0' * data_blocks_number, offset=0)
        driver.write(self.bitmap.offset, self.bitmap.dumped)

        self._driver = driver
        self._block_size = block_size
        self._inode_sector_offset = self.bitmap.offset+self.bitmap.size+1
        self._data_sector_offset = self._inode_sector_offset + 1 + self.inode_size*inodes_number

        self._root_directory = self.create_directory('/')

    def create_directory(self, name):
        # d = Directory(name, data=['.', '..'])
        data = Data(['.', '..'])
        data_size = len(data.dumped)
        required_blocks_number = 0
        while required_blocks_number * self._block_size < data_size:
            required_blocks_number += 1

        addresses = self.get_free_blocks(required_blocks_number)

        # chunks = [data.dumped[i:i+required_blocks_number] for i in range(0, data_size, required_blocks_number)]
        chunks = list(split(data.dumped, self._block_size))
        assert len(addresses) == len(chunks)
        for data_chunk, addr in zip(chunks, addresses):
            self._driver.write(self._data_sector_offset+addr, data_chunk)

        self.bitmap = self.bitmap.update('1', addresses)
        self._driver.write(self.bitmap.offset, self.bitmap.dumped)


        # print(loads(self._driver.read(self.bitmap.offset, self.bitmap.size)))
        #
        # print(loads(self._driver.read(self._data_sector_offset, self._block_size)))


        inode = Inode(name, 'd', 2, data_size, addresses)
        self._driver.write(self._inode_sector_offset, inode.dumped)

        return Directory(inode)

        # blocks_addr = loads(self._driver.read(self._inode_sector_offset, self.inode_size))['data_blocks_map']
        # res = []
        # for addr in blocks_addr:
        #     res.append(self._driver.read(self._data_sector_offset+addr, self._block_size))
        # print(loads(b''.join(res)))


        # print(len(inode.dumped))
        # print(loads(self._driver.read(self._inode_sector_offset, self.inode_size)))







        # required_blocks_number = data.size//self.block_size
        # addresses = get_free_blocks(required_blocks_number)
        # self._driver.write(address=address, data=data)
        # self._driver.write(bitmap)

        # inode = Inode(name=name, file_type='d', links_cnt=2, file_size=data.size, data_blocks=addresses)

        # self._driver.write(address=0, data=inode)
        #

        # return Directory(inode)

    def get_free_blocks(self, n: int) -> list[Address]:
        bitmap = loads(self._driver.read(self.bitmap.offset, self.bitmap.size))
        free_blocks = [m.start() for m in re.finditer('0', bitmap)]
        return free_blocks[:n]




class Inode:
    def __init__(self, file_name: str, file_type: str, links_cnt: int, file_size: Byte, data_blocks: list[Address]):
        self._attrs = {
            'file_name': file_name,
            'file_type': file_type,
            'links_count': links_cnt,
            'file_size': file_size,
            'data_blocks_map': data_blocks
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
        return Bitmap(''.join(bitmap_array))


class File:
    pass

class Directory(File):
    def __init__(self, inode: Inode):
        self._inode = inode


def split(arr, chunk_size):
    chunks = []
    for i in range(0, len(arr), chunk_size):
        chunks.append(arr[i:i+chunk_size])

    return chunks
