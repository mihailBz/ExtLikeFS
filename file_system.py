import re
from pathlib import PurePosixPath
from pickle import dumps, loads
from typing import Type

from driver import Driver
from files import File, Directory, Symlink, RegularFile
from writable import Bitmap, Inode, Data
from fs_exceptions import *

Byte = int
Address = int


class FileSystem:
    __inode_size = 256
    __max_opened_files_number = 10000

    def __init__(
        self,
        driver: Driver,
        block_size: Byte,
        inodes_number: int,
        use_existing: bool = False,
    ) -> None:
        self.data_blocks_number = self._calculate_data_blocks_number(
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

        if not use_existing:
            self._create_directory("/")
        self._cwd = PurePosixPath("/")

        self._opened_files = {}

    def ls(self) -> str:
        return str(self._read_directory(self._cwd))

    def stat(self, path: str) -> Inode:
        inode_id = self._get_file_inode_id(
            self._resolve_path(path), return_symlink_inode_id=True
        )
        inode = self._read_inode(inode_id)
        return inode

    def create(self, path: str) -> None:
        self._create_file(path=PurePosixPath(path), file_cls=RegularFile)

    def open(self, path: str) -> int:
        if len(self._opened_files) > self.__max_opened_files_number:
            raise TooManyFilesOpened

        inode_id = self._get_file_inode_id(self._resolve_path(path))
        inode = self._read_inode(inode_id)
        addresses = inode.content.get("data_blocks_map")
        if len(addresses) == 0:
            data = None
        else:
            data = self._read_data(addresses)
        file_descriptor = max(self._opened_files, default=0) + 1
        self._opened_files[file_descriptor] = RegularFile(inode, data)
        return file_descriptor

    def close(self, fd: int) -> None:
        if fd in self._opened_files:
            self._opened_files.pop(fd)
        else:
            raise WrongFileDescriptorNumber

    def seek(self, fd: int, seek: int) -> None:
        if fd in self._opened_files:
            self._opened_files.get(fd).seek = seek
        else:
            raise WrongFileDescriptorNumber

    def read(self, fd: int, size: Byte) -> bytes:
        if fd in self._opened_files:
            read_value: bytes = self._opened_files.get(fd).read(size)
            return read_value
        else:
            raise WrongFileDescriptorNumber

    def write(self, fd: int, data: bytes, size: Byte) -> None:
        if fd in self._opened_files:
            file: RegularFile = self._opened_files.get(fd)
            updated_file: RegularFile = file.write(data, size)
            file_data: Data = updated_file.data
            inode_record: dict = updated_file.inode.content
            addresses = self._allocate_blocks(file_data)
            size = len(file_data.dumped)
            self._write_data(addresses, file_data)

            self._clear_data_block(inode_record["data_blocks_map"])

            inode_record["file_size"] = size
            inode_record["data_blocks_map"] = addresses
            inode = Inode(inode_record)
            self._write_inode(inode)

            self._opened_files[fd] = RegularFile(inode, file_data, file.seek)

        else:
            raise WrongFileDescriptorNumber

    def link(self, file_path: str, link_path: str) -> None:
        f_path: PurePosixPath = self._resolve_path(file_path)
        l_path: PurePosixPath = self._resolve_path(link_path)

        inode: Inode = self._read_inode(self._get_file_inode_id(f_path))
        inode_record: dict = inode.content
        if inode_record.get("file_type") == "d":
            raise DirectoryLinkException("Cannot create hardlink for directory")

        inode_record["file_name"].append(l_path.name)
        inode_record["links_cnt"] += 1

        l_parent_directory: Directory = self._read_directory(l_path.parent)
        self._add_file_to_parent_directory_entry(
            l_parent_directory,
            l_path.name,
            inode_record["id"],
            inode_record["file_type"],
        )

        self._write_inode(Inode(inode_record))

    def unlink(self, path: str) -> None:
        path: PurePosixPath = self._resolve_path(path)
        inode_id: int = self._get_file_inode_id(path)
        for open_file in self._open_files.values():
            if open_file.inode.content.get("id") == inode_id:
                raise CannotUnlinkOpenFile
        inode: Inode = self._read_inode(inode_id)
        inode_record: dict = inode.content

        if inode_record.get("file_type") == "d":
            raise DirectoryLinkException("Cannot unlink directory")

        inode_record["file_name"].remove(path.name)
        inode_record["links_cnt"] -= 1

        if inode_record["links_cnt"] == 0:
            self._clear_data_block(inode_record["data_blocks_map"])
            self._clear_inode(inode_record["id"])

        parent: Directory = self._read_directory(path.parent)

        self._remove_file_from_parent_directory_entry(parent, path.name)
        self._write_inode(Inode(inode_record))

    def truncate(self, path: str, size: int) -> None:
        path: PurePosixPath = self._resolve_path(path)

        inode: Inode = self._read_inode(self._get_file_inode_id(path))
        addresses = inode.content.get("data_blocks_map")
        if len(addresses) == 0:
            data = None
        else:
            data = self._read_data(addresses)

        file: RegularFile = RegularFile(inode, data).truncate(size)
        file_data: Data = file.data
        inode_record: dict = file.inode.content
        size = len(file_data.dumped)
        self._write_data(addresses, file_data)

        inode_record["file_size"] = size
        inode_record["data_blocks_map"] = addresses

        self._write_inode(Inode(inode_record))

    def mkdir(self, path: str) -> None:
        if path == "/":
            raise FileAlreadyExists
        else:
            self._create_directory(path)

    def rmdir(self, path: str) -> None:
        path: PurePosixPath = self._resolve_path(path)
        if str(path) == "/":
            raise CannotRemoveDirectory("root directory cannot be removed")

        directory: Directory = self._read_directory(path)
        parent: Directory = self._read_directory(path.parent)

        if len(directory.data.content) > 2:
            raise CannotRemoveDirectory("directory is not empty")

        self._clear_data_block(directory.inode.content["data_blocks_map"])
        self._clear_inode(directory.inode.content["id"])

        self._remove_file_from_parent_directory_entry(parent, path.name)

    def cd(self, path: str) -> None:
        self.cwd = self._absolutize(self._resolve_path(path))

    def symlink(self, file_path: str, link_path: str) -> None:
        c_path = self._resolve_path(file_path)
        s_path = self._resolve_path(link_path)
        data = Data(str(c_path))
        if len(data.dumped) > self._block_size:
            raise TooLongSymlink

        self._create_file(path=s_path, data=data, file_cls=Symlink)

    @property
    def cwd(self) -> PurePosixPath:
        return self._cwd

    @cwd.setter
    def cwd(self, path: PurePosixPath) -> None:
        self._cwd = path

    @staticmethod
    def _calculate_data_blocks_number(
        device_size: int, block_size: int, inodes_number: int, inodes_size: int
    ) -> int:
        data_blocks_number = (device_size - (inodes_number * inodes_size)) // block_size
        bitmap_blocks_number = 0

        while bitmap_blocks_number * block_size - len(dumps("")) < data_blocks_number:
            bitmap_blocks_number += 1
        data_blocks_number -= bitmap_blocks_number
        return data_blocks_number

    def _create_directory(self, path: str) -> None:
        path: PurePosixPath = self._resolve_path(path)
        if str(path) == "/":
            inode_id = 0
            entry = Data(
                {
                    ".": inode_id,
                    "..": inode_id,
                }
            )
            self._create_file(
                path=path, data=entry, file_cls=Directory, name="/", inode_id=inode_id
            )
        else:
            parent: Directory = self._read_directory(path.parent)
            inode_id = self._get_free_inode()
            entry = Data(
                {
                    ".": inode_id,
                    "..": parent.inode.content.get("id"),
                }
            )
            name = path.name
            self._create_file(
                path=path,
                data=entry,
                file_cls=Directory,
                name=name,
                parent=parent,
                inode_id=inode_id,
            )

    def _read_directory(self, path: PurePosixPath) -> Directory:
        inode_id = self._get_file_inode_id(path)
        inode = self._read_inode(inode_id)
        entry = self._read_data(inode.content.get("data_blocks_map"))
        return Directory(inode, entry)

    def _get_file_inode_id(
        self, path: PurePosixPath, return_symlink_inode_id: bool = False
    ) -> int:
        inode_id = 0
        if len(path.parents) != 0:
            parents = list(path.parents[::-1])
            parents.append(path)
        else:
            return inode_id
        for child in parents[1:]:
            parent_entry = self._read_file(inode_id)
            if parent_entry.content.get(child.name) is not None:
                inode_id: int = parent_entry.content.get(child.name)
                inode: Inode = self._read_inode(inode_id)
                if inode.content.get("file_type") == "l":
                    data: str = self._read_data(
                        inode.content.get("data_blocks_map")
                    ).content
                    symlink_contained_path: PurePosixPath = PurePosixPath(data)
                    if (
                        return_symlink_inode_id
                        and path.name == inode.content.get("file_name")[0]
                    ):
                        return inode_id
                    inode_id: int = self._get_file_inode_id(symlink_contained_path)

            else:
                raise FileDoesNotExist
        return inode_id

    def _read_file(self, inode_id) -> Data:
        inode: Inode = self._read_inode(inode_id)
        data_blocks_addresses = inode.content.get("data_blocks_map")
        return self._read_data(data_blocks_addresses)

    def _read_inode(self, inode_id: int) -> Inode:
        return Inode(
            loads(
                self._driver.read(
                    self._inode_sector_offset + inode_id * self.__inode_size,
                    self.__inode_size,
                )
            )
        )

    def _read_data(self, addr_arr: list[Address]) -> Data:
        data = []
        for data_block_addr in addr_arr:
            data.append(
                self._driver.read(
                    self._data_sector_offset + data_block_addr * self._block_size,
                    self._block_size,
                )
            )
        return Data(loads(b"".join(data)))

    def _get_free_inode(self) -> int:
        for i in range(self._inodes_number):
            if (
                self._driver.read(
                    self._inode_sector_offset + i * self.__inode_size, self.__inode_size
                )
                == b"\x00"
            ):
                return i
        raise OutOfInodes

    def _write_data(self, addresses: list[Address], data: Data) -> None:
        chunks = data.split(self._block_size)
        assert len(addresses) == len(chunks)
        for data_chunk, addr in zip(chunks, addresses):
            self._driver.write(
                self._data_sector_offset + addr * self._block_size, data_chunk
            )
        self.bitmap = self.bitmap.update("1", addresses)
        self._driver.write(self.bitmap.offset, self.bitmap.dumped)

    def _allocate_blocks(self, data: Data) -> list[Address]:

        required_blocks_number = 0
        while required_blocks_number * self._block_size < len(data.dumped):
            required_blocks_number += 1
        return self._get_free_blocks(required_blocks_number)

    def _get_free_blocks(self, n: int) -> list[Address]:
        bitmap = loads(self._driver.read(self.bitmap.offset, self.bitmap.size))
        if "0" not in bitmap:
            raise OutOfBlocks
        free_blocks = [m.start() for m in re.finditer("0", bitmap)]
        return free_blocks[:n]

    def _write_inode(self, inode: Inode) -> None:
        self._driver.write(
            self._inode_sector_offset + inode.content.get("id") * self.__inode_size,
            inode.dumped,
        )

    def _clear_data_block(self, addresses: list[Address]) -> None:
        for addr in addresses:
            self._driver.clear(
                self._data_sector_offset + addr * self._block_size, self._block_size
            )
        self.bitmap = self.bitmap.update("0", addresses)
        self._driver.write(self.bitmap.offset, self.bitmap.dumped)

    def _clear_inode(self, inode_id: int) -> None:
        self._driver.clear(
            self._inode_sector_offset + inode_id * self.__inode_size, self.__inode_size
        )

    def _resolve_path(self, path: str) -> PurePosixPath:
        path = PurePosixPath(path)
        if path.is_absolute():
            return path
        else:
            return self._cwd.joinpath(path)

    def _create_file(
        self,
        path: PurePosixPath,
        file_cls: Type[File],
        data: Data = None,
        name: str = None,
        parent: Directory = None,
        inode_id: int = None,
    ) -> None:
        if file_cls.ftype != "d":
            name = path.name
            parent = self._read_directory(path.parent)
            inode_id = self._get_free_inode()

        if not (file_cls.ftype == "d" and name == "/"):
            self._add_file_to_parent_directory_entry(
                parent, name, inode_id, file_cls.ftype
            )

        if data is not None:
            addresses = self._allocate_blocks(data)
            size = len(data.dumped)
            self._write_data(addresses, data)
        else:
            size = 0
            addresses = []

        inode_record = {
            "id": inode_id,
            "file_name": [name],
            "file_type": file_cls.ftype,
            "links_cnt": file_cls.default_links_cnt,
            "file_size": size,
            "data_blocks_map": addresses,
        }
        self._write_inode(Inode(inode_record))

    def _remove_file_from_parent_directory_entry(
        self, parent: Directory, child_name: str
    ) -> None:
        parent_entry: dict = parent.data.content
        parent_entry.pop(child_name)
        parent_entry: Data = Data(parent_entry)

        parent_inode_record = parent.inode.content
        parent_inode_record["links_cnt"] -= 1
        addresses = parent_inode_record["data_blocks_map"]

        # todo test
        if (
            self._block_size * len(parent_inode_record["data_blocks_map"])
            - len(parent_entry.dumped)
            > self._block_size
        ):
            self._clear_data_block(parent_inode_record["data_blocks_map"])
            addresses = self._allocate_blocks(parent_entry)
            parent_inode_record["data_blocks_map"] = addresses
            parent_inode_record["file_size"] = len(parent_entry.dumped)
        self._write_data(addresses, parent_entry)
        self._write_inode(Inode(parent_inode_record))

    def _add_file_to_parent_directory_entry(
        self, parent: Directory, child_name: str, child_inode_id: int, child_type: str
    ) -> None:
        parent_entry = parent.data.content
        if child_name not in parent_entry:
            parent_inode_record = parent.inode.content

            if child_type == "d":
                parent_inode_record["links_cnt"] += 1

            parent_entry[child_name] = child_inode_id
            if len(dumps(parent_entry)) > self._block_size * len(
                parent_inode_record["data_blocks_map"]
            ):
                parent_inode_record["data_blocks_map"].extend(self._get_free_blocks(1))
            self._write_inode(Inode(parent_inode_record))
            self._write_data(parent_inode_record["data_blocks_map"], Data(parent_entry))
        else:
            raise FileAlreadyExists

    @staticmethod
    def _absolutize(path: PurePosixPath):
        split_path: list = list(path.parts)
        i = 0
        try:
            while i < len(split_path):
                if split_path[i] == "..":
                    split_path.pop(i)
                    split_path.pop(i - 1)
                    i -= 2
                i += 1
        except IndexError:
            return PurePosixPath("/")
        return PurePosixPath("/").joinpath("/".join(split_path[1:]))
