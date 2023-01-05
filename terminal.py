from device import StorageDevice
from driver import Driver
from file_system import FileSystem
from fs_exceptions import InvalidInput, FileSystemException
import re

Byte = int
Address = int


def mkfs(inodes_number: int) -> FileSystem:
    use_existing_fs = False
    block_size: Byte = 4096
    disk_size: Byte = block_size * 50

    # inodes_number = 2000

    storage_device = StorageDevice(disk_size, "storage", use_existing=use_existing_fs)
    driver = Driver(storage_device)
    return FileSystem(driver, block_size, inodes_number, use_existing=use_existing_fs)


def default_cmd(*args, **kwargs):
    raise InvalidInput


map_cmd = {
    "ls": FileSystem.ls,
    "mkfs": mkfs,
    "stat": FileSystem.stat,
    "create": FileSystem.create,
    "unlink": FileSystem.unlink,
    "mkdir": FileSystem.mkdir,
    "rmdir": FileSystem.rmdir,
    "cd": FileSystem.cd,
    "open": FileSystem.open,
    "close": FileSystem.close,
    "seek": FileSystem.seek,
    "read": FileSystem.read,
    "write": FileSystem.write,
    "link": FileSystem.link,
    "symlink": FileSystem.symlink,
    "truncate": FileSystem.truncate,
}


class Terminal:
    def start_session(self):

        initial_input = input("fs> ").strip()
        match = re.fullmatch(r"mkfs\s+(\d+)", initial_input)
        while not match:
            initial_input = input("fs> ").strip()
            match = re.fullmatch(r"mkfs\s+(\d+)", initial_input)

        fs = mkfs(int(match.group(1)))

        descriptors = {}

        while True:
            try:
                user_input: str = input(f"fs@fs:{fs.cwd}$ ").strip()
                if re.fullmatch(r"ls", user_input):
                    command = map_cmd.get("ls", default_cmd)
                    out = command(fs)
                    if out is not None:
                        print(out)
                elif match := re.fullmatch(
                    r"(\w+)\s*=\s*open\s*(.+)", user_input
                ):  # open
                    command = map_cmd.get("open", default_cmd)

                    fd_var_name = match.group(1)
                    fd = command(fs, match.group(2))
                    descriptors[fd_var_name] = fd

                elif match := re.fullmatch(
                    r"write\s+(\w+)\s+(\w+)\s+(\d+)", user_input
                ):  # write
                    command = map_cmd.get("write", default_cmd)
                    fd = descriptors.get(match.group(1))
                    if fd is None:
                        raise InvalidInput
                    data = match.group(2).encode()
                    size = int(match.group(3))
                    command(fs, fd, data, size)
                elif match := re.fullmatch(r"close\s+(\w+)", user_input):  # close
                    command = map_cmd.get("close", default_cmd)
                    fd = descriptors.get(match.group(1))
                    if fd is None:
                        raise InvalidInput

                    command(fs, fd)
                elif match := re.fullmatch(
                    r"truncate\s+(.+)\s+(\d+)", user_input
                ):  # truncate
                    command = map_cmd.get("truncate", default_cmd)
                    path = match.group(1)
                    size = int(match.group(2))
                    command(fs, path, size)

                elif match := re.fullmatch(
                    r"(\w+)\s+(\w+)\s+(\d+)", user_input
                ):  # seek read
                    command = map_cmd.get(match.group(1), default_cmd)
                    fd = descriptors.get(match.group(2))
                    size = int(match.group(3))
                    if fd is None:
                        raise InvalidInput

                    out = command(fs, fd, size)
                    if out:
                        print(out.decode())

                elif match := re.fullmatch(
                    r"(\w+)\s+(.+)\s+(.+)", user_input
                ):  # link symlink
                    command = map_cmd.get(match.group(1), default_cmd)
                    path1 = match.group(2)
                    path2 = match.group(3)

                    command(fs, path1, path2)

                elif match := re.fullmatch(
                    r"(\w+)\s+(.+)", user_input
                ):  # stat create unlink mkdir rmdir cd
                    command = map_cmd.get(match.group(1), default_cmd)
                    out = command(fs, match.group(2))
                    if out is not None:
                        print(out)

                elif re.fullmatch(r"\s*", user_input):
                    pass
                else:
                    raise InvalidInput
            except FileSystemException as e:
                print(e.__class__.__name__)
