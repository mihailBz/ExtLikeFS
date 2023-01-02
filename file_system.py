import re
from pathlib import PurePosixPath
from pickle import dumps, loads

from driver import Driver
from files import Directory
from writable import Bitmap, Inode, Data
from exceptions import *

Byte = int
Address = int


class FileSystem:
    __inode_size = 256

    def __init__(self, driver: Driver, block_size: Byte, inodes_number: int):
        self.data_blocks_number = self.calculate_data_blocks_number(
            driver.device_size,
            block_size,
            inodes_number,
            self.__inode_size
        )
        self._driver = driver

        self.bitmap = Bitmap("0" * self.data_blocks_number, offset=0)
        self._driver.write(self.bitmap.offset, self.bitmap.dumped)

        self._block_size = block_size
        self._inode_sector_offset = self.bitmap.offset + self.bitmap.size + 1
        self._inodes_number = inodes_number
        self._data_sector_offset = self._inode_sector_offset + 1 + self.__inode_size * self._inodes_number

        self._root_directory = self.__mkdir(PurePosixPath('/'))
        self._cwd = self._root_directory

    @staticmethod
    def calculate_data_blocks_number(device_size, block_size, inodes_number, inodes_size):
        data_blocks_number = (device_size - (inodes_number * inodes_size)) // block_size
        bitmap_blocks_number = 0

        while bitmap_blocks_number * block_size - len(dumps("")) < data_blocks_number:
            bitmap_blocks_number += 1
        data_blocks_number -= bitmap_blocks_number
        return data_blocks_number

    def mkdir(self, path: PurePosixPath) -> None:
        if str(path) == '/':
            raise FileAlreadyExists
        else:
            self.__mkdir(path)

    def __mkdir(self, path: PurePosixPath) -> None:
        if str(path) == '/':
            name = '/'
            inode_id = 0
            entry = Data({
                '.': inode_id,
                '..': inode_id,
            })
        else:
            parent: Directory = self.read_directory(path.parent)

            name = path.name
            inode_id = self.get_free_inode()
            entry = Data({
                '.': inode_id,
                '..': parent.inode.content.get('id'),
            })

            parent_entry = parent.data.content
            if name not in parent_entry:

                parent_inode_record = parent.inode.content
                parent_inode_record['links_cnt'] += 1

                parent_entry[name] = inode_id
                if len(dumps(parent_entry)) > self._block_size * len(parent_inode_record['data_blocks_map']):
                    parent_inode_record['data_blocks_map'].extend(self.get_free_blocks(1))

                self.write_inode(Inode(parent_inode_record))
                self.write_data(parent_inode_record['data_blocks_map'], Data(parent_entry))
            else:
                raise FileAlreadyExists

        addresses = self.allocate_blocks(entry)
        self.write_data(addresses, entry)
        inode_record = {
            'id': inode_id,
            'file_name': name,
            'file_type': 'd',
            'links_cnt': 2,
            'file_size': len(entry.dumped),
            'data_blocks_map': addresses
        }
        self.write_inode(Inode(inode_record))

    def read_directory(self, path: PurePosixPath) -> Directory:
        inode_id = self.get_file_inode_id(path)
        inode = self.read_inode(inode_id)
        entry = self.read_data(inode.content.get('data_blocks_map'))
        return Directory(inode, entry)

    def get_file_inode_id(self, path: PurePosixPath) -> int:
        if path.is_absolute():
            inode_id = 0
            if len(path.parents) != 0:
                parents = list(path.parents[::-1])
                parents.append(path)
            else:
                return inode_id
            for parent, child in zip(parents[:-1], parents[1:]):
                parent_entry = self.read_file(inode_id)
                if parent_entry.content.get(child.name):
                    inode_id = parent_entry.content.get(child.name)
                else:
                    raise FileDoesNotExist
            return inode_id

    def read_file(self, inode_id) -> Data:
        inode: Inode = self.read_inode(inode_id)
        data_blocks_addresses = inode.content.get('data_blocks_map')
        return self.read_data(data_blocks_addresses)

    def read_inode(self, inode_id: int) -> Inode:
        return Inode(
            loads(self._driver.read(self._inode_sector_offset + inode_id * self.__inode_size, self.__inode_size)))

    def read_data(self, addr_arr: list[Address]) -> Data:
        data = []
        for data_block_addr in addr_arr:
            data.append(self._driver.read(
                self._data_sector_offset + data_block_addr * self._block_size,
                self._block_size
            ))
        return Data(loads(b''.join(data)))

    def get_free_inode(self):
        for i in range(self._inodes_number):
            if (
                    self._driver.read(
                        self._inode_sector_offset + i * self.__inode_size, self.__inode_size
                    )
                    == b"\x00"
            ):
                return i
        raise OutOfInodes

    def write_data(self, addresses: list[Address], data: Data):
        chunks = data.split(self._block_size)
        assert len(addresses) == len(chunks)
        for data_chunk, addr in zip(chunks, addresses):
            self._driver.write(
                self._data_sector_offset + addr * self._block_size, data_chunk
            )
        self.bitmap = self.bitmap.update("1", addresses)
        self._driver.write(self.bitmap.offset, self.bitmap.dumped)

    def allocate_blocks(self, data: Data) -> list[Address]:

        required_blocks_number = 0
        while required_blocks_number * self._block_size < len(data.dumped):
            required_blocks_number += 1
        return self.get_free_blocks(required_blocks_number)

    def get_free_blocks(self, n: int):
        bitmap = loads(self._driver.read(self.bitmap.offset, self.bitmap.size))
        if '0' not in bitmap:
            raise OutOfBlocks
        free_blocks = [m.start() for m in re.finditer("0", bitmap)]
        return free_blocks[:n]

    def write_inode(self, inode: Inode):
        self._driver.write(
            self._inode_sector_offset + inode.content.get('id') * self.__inode_size,
            inode.dumped
        )

# class FileSystem:
#     inode_size: Byte = 256
#
#     def __init__(self, driver: Driver, block_size: Byte, inodes_number: int):
#
#         data_blocks_number = (
#                                      driver.device_size - (inodes_number * self.inode_size)
#                              ) // block_size
#         bitmap_blocks_number = 0
#
#         # 15 bytes - dumped empty string size
#         while bitmap_blocks_number * block_size - len(dumps("")) < data_blocks_number:
#             bitmap_blocks_number += 1
#         data_blocks_number -= bitmap_blocks_number
#
#         self.bitmap = Bitmap("0" * data_blocks_number, offset=0)
#         driver.write(self.bitmap.offset, self.bitmap.dumped)
#
#         self._driver = driver
#         self._block_size = block_size
#         self._inode_sector_offset = self.bitmap.offset + self.bitmap.size + 1
#         self._inodes_number = inodes_number
#         self._data_sector_offset = (
#                 self._inode_sector_offset + 1 + self.inode_size * inodes_number
#         )
#
#         # self._root_directory = self.create_directory("/", Directory)
#         self._root_directory = self.create_file("/", [(0, '/'), (0, '/'), ], Directory)
#
#     def create_directory(self, name, file_cls, data=None):
#
#         path = Path(name)
#         inode_id = self.get_free_inode()
#         if name == '/':
#             data = Data([
#                 (inode_id, name),
#                 (inode_id, name),
#             ])
#         else:
#             data = Data([
#                 (inode_id, path.split()[-1]),
#                 ()
#             ])
#
#     def create_file(self, name, data, file_cls):
#         data = Data(data)
#         data_size = len(data.dumped)
#
#         required_blocks_number = 0
#         while required_blocks_number * self._block_size < data_size:
#             required_blocks_number += 1
#
#         addresses = self.get_free_blocks(required_blocks_number)
#
#         chunks = data.split(self._block_size)
#         assert len(addresses) == len(chunks)
#         for data_chunk, addr in zip(chunks, addresses):
#             self._driver.write(
#                 self._data_sector_offset + addr * self._block_size, data_chunk
#             )
#
#         self.bitmap = self.bitmap.update("1", addresses)
#         self._driver.write(self.bitmap.offset, self.bitmap.dumped)
#
#         inode_id = self.get_free_inode()
#         inode = Inode(
#             name, file_cls.ftype, file_cls.default_links_cnt, data_size, addresses
#         )
#
#         self._driver.write(
#             self._inode_sector_offset + inode_id * self.inode_size, inode.dumped
#         )
#
#         print(
#             f"bitmap: {loads(self._driver.read(self.bitmap.offset, self.bitmap.size))}"
#         )
#         if file_cls.ftype == 'd':
#             print(
#                 f"rootdir inode: {loads(self._driver.read(self._inode_sector_offset, self.inode_size))}"
#             )
#             print(
#                 f"rootdir: {loads(self._driver.read(self._data_sector_offset, self._block_size))}"
#             )
#
#         if file_cls.ftype == "f":
#             print(
#                 f"file inode: {loads(self._driver.read(self._inode_sector_offset + 1 * self.inode_size, self.inode_size))}"
#             )
#             addr = self._data_sector_offset + 1 * self._block_size
#             n_bytes = self._block_size
#             print(f"file: {loads(self._driver.read(addr, n_bytes))}")
#
#         return file_cls(inode)
#
#     def get_free_blocks(self, n: int) -> list[Address]:
#         bitmap = loads(self._driver.read(self.bitmap.offset, self.bitmap.size))
#         free_blocks = [m.start() for m in re.finditer("0", bitmap)]
#         return free_blocks[:n]
#
#     def get_free_inode(self):
#         for i in range(self._inodes_number):
#             if (
#                     self._driver.read(
#                         self._inode_sector_offset + i * self.inode_size, self.inode_size
#                     )
#                     == b"\x00"
#             ):
#                 return i
#         raise OutOfInodes
#
#     def get_file_inode(self, path: Path):
#         if path.is_abs:
#             dir_entry = self.read_data_by_inode(0)
#             for d1, d2 in zip(path.split()[:-1], path.split()[1:]):
#                 for i, d_entry in enumerate(dir_entry):
#                     if d2 == d_entry[0]:
#                         inode_id = d_entry[1]
#                         dir_entry = self.read_data_by_inode(inode_id)
#                         break
#                     if i == len(dir_entry) and d2 != d_entry[0]:
#                         raise FileDoesNotExist
#             return inode_id
#
#     def read_data_by_inode(self, inode_id):
#         inode_data = loads(self._driver.read(self._inode_sector_offset + inode_id * self.inode_size, self.inode_size))
#         data = []
#         for data_block_addr in inode_data.get('data_blocks_map'):
#             data.append(self._driver.read(
#                 self._data_sector_offset + data_block_addr * self._block_size,
#                 self._block_size
#             ))
#         return loads(b''.join(data))
