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

        self._bitmap_offset = 0

        bitmap = dumps('0' * data_blocks_number)
        driver.write(self._bitmap_offset, bitmap)
        self._bitmap_size = len(bitmap)

        self._driver = driver
        self._block_size = block_size

    def create_directory(self, name):
        # d = Directory(name, data=['.', '..'])
        data = Data(".;..")
        data_size = len(data.dumped)
        required_blocks_number = 0
        while required_blocks_number * self._block_size < data_size:
            required_blocks_number += 1

        addresses = self.get_free_blocks(required_blocks_number)
        chunks = [data.dumped[i:i+required_blocks_number] for i in range(0, data_size, required_blocks_number)]
        assert len(addresses) == len(chunks)
        for data_chunk, addr in zip(chunks, addresses):
            self._driver.write(addr, data_chunk)



        # required_blocks_number = data.size//self.block_size
        # addresses = get_free_blocks(required_blocks_number)
        # self._driver.write(address=address, data=data)
        # self._driver.write(bitmap)

        # inode = Inode(name=name, file_type='d', links_cnt=2, file_size=data.size, data_blocks=addresses)

        # self._driver.write(address=0, data=inode)
        #

        # return Directory(inode)

    def get_free_blocks(self, n: int) -> list[Address]:
        bitmap = loads(self._driver.read(self._bitmap_offset, self._bitmap_size))
        free_blocks = [m.start() for m in re.finditer('0', bitmap)]
        return free_blocks[:n]


class File:
    pass


class Directory(File):
    def __init__(self, name: str, data):
        self._name = name
        self._data = data


class Inode:
    def __init__(self, file_name: str, file_type: str):
        pass


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

