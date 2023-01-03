import re
from pathlib import PurePosixPath
from pickle import dumps, loads
from typing import Type

from driver import Driver
from files import File, Directory, Symlink, RegularFile
from writable import Bitmap, Inode, Data
from exceptions import *

Byte = int
Address = int


class FileSystem:
    __inode_size = 256

    def __init__(self, driver: Driver, block_size: Byte, inodes_number: int):
        self.data_blocks_number = self.calculate_data_blocks_number(
            driver.device_size, block_size, inodes_number, self.__inode_size
        )
        self._driver = driver

        self.bitmap = Bitmap("0" * self.data_blocks_number, offset=0)
        self._driver.write(self.bitmap.offset, self.bitmap.dumped)

        self._block_size = block_size
        self._inode_sector_offset = self.bitmap.offset + self.bitmap.size + 1
        self._inodes_number = inodes_number
        self._data_sector_offset = (
            self._inode_sector_offset + 1 + self.__inode_size * self._inodes_number
        )

        # self._root_directory_path = PurePosixPath("/")
        self.create_directory("/")
        self._cwd = PurePosixPath("/")

    @staticmethod
    def calculate_data_blocks_number(
        device_size, block_size, inodes_number, inodes_size
    ):
        data_blocks_number = (device_size - (inodes_number * inodes_size)) // block_size
        bitmap_blocks_number = 0

        while bitmap_blocks_number * block_size - len(dumps("")) < data_blocks_number:
            bitmap_blocks_number += 1
        data_blocks_number -= bitmap_blocks_number
        return data_blocks_number

    def mkdir(self, path: str) -> None:
        if path == "/":
            raise FileAlreadyExists
        else:
            self.create_directory(path)

    def create_directory(self, path: str) -> None:
        path: PurePosixPath = self.resolve_path(path)
        if str(path) == "/":
            inode_id = 0
            entry = Data(
                {
                    ".": inode_id,
                    "..": inode_id,
                }
            )
            self.create_file(
                path=path, data=entry, file_cls=Directory, name="/", inode_id=inode_id
            )
        else:
            parent: Directory = self.read_directory(path.parent)
            inode_id = self.get_free_inode()
            entry = Data(
                {
                    ".": inode_id,
                    "..": parent.inode.content.get("id"),
                }
            )
            name = path.name
            self.create_file(
                path=path,
                data=entry,
                file_cls=Directory,
                name=name,
                parent=parent,
                inode_id=inode_id,
            )

    def read_directory(self, path: PurePosixPath) -> Directory:
        inode_id = self.get_file_inode_id(path)
        inode = self.read_inode(inode_id)
        entry = self.read_data(inode.content.get("data_blocks_map"))
        return Directory(inode, entry)

    def get_file_inode_id(self, path: PurePosixPath) -> int:
        inode_id = 0
        if len(path.parents) != 0:
            parents = list(path.parents[::-1])
            parents.append(path)
        else:
            return inode_id
        for parent, child in zip(parents[:-1], parents[1:]):
            parent_entry = self.read_file(inode_id)
            if parent_entry.content.get(child.name) is not None:
                inode_id = parent_entry.content.get(child.name)
            else:
                raise FileDoesNotExist
        return inode_id

    def read_file(self, inode_id) -> Data:
        inode: Inode = self.read_inode(inode_id)
        data_blocks_addresses = inode.content.get("data_blocks_map")
        return self.read_data(data_blocks_addresses)

    def read_inode(self, inode_id: int) -> Inode:
        return Inode(
            loads(
                self._driver.read(
                    self._inode_sector_offset + inode_id * self.__inode_size,
                    self.__inode_size,
                )
            )
        )

    def read_data(self, addr_arr: list[Address]) -> Data:
        data = []
        for data_block_addr in addr_arr:
            data.append(
                self._driver.read(
                    self._data_sector_offset + data_block_addr * self._block_size,
                    self._block_size,
                )
            )
        return Data(loads(b"".join(data)))

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
        if "0" not in bitmap:
            raise OutOfBlocks
        free_blocks = [m.start() for m in re.finditer("0", bitmap)]
        return free_blocks[:n]

    def write_inode(self, inode: Inode):
        self._driver.write(
            self._inode_sector_offset + inode.content.get("id") * self.__inode_size,
            inode.dumped,
        )

    def rmdir(self, path: str):
        path: PurePosixPath = self.resolve_path(path)
        if str(path) == "/":
            raise CannotRemoveDirectory("root directory cannot be removed")

        directory: Directory = self.read_directory(path)
        parent: Directory = self.read_directory(path.parent)

        if len(directory.data.content) > 2:
            raise CannotRemoveDirectory("directory is not empty")

        self.clear_data_block(directory.inode.content["data_blocks_map"])
        self.clear_inode(directory.inode.content["id"])

        parent_entry: dict = parent.data.content
        parent_entry.pop(path.name)
        parent_entry: Data = Data(parent_entry)

        parent_inode_record = parent.inode.content
        parent_inode_record["links_cnt"] -= 1
        addresses = parent_inode_record["data_blocks_map"]

        if (
            self._block_size * len(parent_inode_record["data_blocks_map"])
            - len(parent_entry.dumped)
            > self._block_size
        ):
            self.clear_data_block(parent_inode_record["data_blocks_map"])
            addresses = self.allocate_blocks(parent_entry)
            parent_inode_record["data_blocks_map"] = addresses
            parent_inode_record["file_size"] = len(parent_entry.dumped)

        self.write_data(addresses, parent_entry)
        self.write_inode(Inode(parent_inode_record))

    def clear_data_block(self, addresses: list[Address]) -> None:
        for addr in addresses:
            self._driver.clear(
                self._data_sector_offset + addr * self._block_size, self._block_size
            )
        self.bitmap = self.bitmap.update("0", addresses)
        self._driver.write(self.bitmap.offset, self.bitmap.dumped)

    def clear_inode(self, inode_id: int):
        self._driver.clear(
            self._inode_sector_offset + inode_id * self.__inode_size, self.__inode_size
        )

    def ls(self) -> str:
        return str(self.read_directory(self._cwd))

    def stat(self, path: str) -> str:
        return str(self.read_directory(self.resolve_path(path)).inode)

    def resolve_path(self, path: str) -> PurePosixPath:
        path = PurePosixPath(path)
        if path.is_absolute():
            return path
        else:
            return self._cwd.joinpath(path)

    @property
    def cwd(self):
        return self._cwd

    @cwd.setter
    def cwd(self, path: PurePosixPath):
        self._cwd = path

    def cd(self, path: str):
        self.cwd = PurePosixPath(path)

    def create_symlink(self, contained_path: str, symlink_path: str):
        symlink_path = PurePosixPath(symlink_path)
        data = Data(contained_path)
        if len(data.dumped) > self._block_size:
            raise TooLongSymlink

        self.create_file(path=symlink_path, data=data, file_cls=Symlink)

    def create_regular_file(self, path: str):
        self.create_file(path=PurePosixPath(path), file_cls=RegularFile)

    def create_file(
        self,
        path: PurePosixPath,
        file_cls: Type[File],
        data: Data=None,
        name: str = None,
        parent: Directory = None,
        inode_id: int = None,
    ):
        if file_cls.ftype != "d":
            name = path.name
            parent = self.read_directory(path.parent)
            inode_id = self.get_free_inode()

        if not (file_cls.ftype == "d" and name == "/"):
            parent_entry = parent.data.content
            if name not in parent_entry:
                parent_inode_record = parent.inode.content
                parent_inode_record["links_cnt"] += 1

                parent_entry[name] = inode_id
                if len(dumps(parent_entry)) > self._block_size * len(
                    parent_inode_record["data_blocks_map"]
                ):
                    parent_inode_record["data_blocks_map"].extend(
                        self.get_free_blocks(1)
                    )
                self.write_inode(Inode(parent_inode_record))
                self.write_data(
                    parent_inode_record["data_blocks_map"], Data(parent_entry)
                )
            else:
                raise FileAlreadyExists

        if data is not None:
            addresses = self.allocate_blocks(data)
            size = len(data.dumped)
            self.write_data(addresses, data)
        else:
            size = 0
            addresses = []

        inode_record = {
            "id": inode_id,
            "file_name": name,
            "file_type": file_cls.ftype,
            "links_cnt": file_cls.default_links_cnt,
            "file_size": size,
            "data_blocks_map": addresses,
        }
        self.write_inode(Inode(inode_record))
