from writable import Inode, Data


class File:
    ftype = None
    default_links_cnt = None

    def __init__(self, inode: Inode, data: Data):
        self._inode = inode
        self._data = data

    @property
    def data(self):
        return self._data

    @property
    def inode(self):
        return self._inode


class Directory(File):
    ftype = "d"
    default_links_cnt = 2

    def __repr__(self):
        return "\n".join([f"{v} {k}" for k, v in self.data.content.items()])


class RegularFile(File):
    ftype = "f"
    default_links_cnt = 1


class Symlink(File):
    ftype = "l"
    default_links_cnt = 1
