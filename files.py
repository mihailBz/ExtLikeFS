from writable import Inode, Data


class File:
    def __init__(self, inode: Inode, data: Data):
        self._inode = inode
        self._data = data

    @property
    def data(self):
        return self._data

    @property
    def inode(self):
        return self._inode

    def __str__(self):
        return str(self.data.content)


class Directory(File):
    ftype = "d"
    default_links_cnt = 2


class RegularFile(File):
    ftype = "f"
    default_links_cnt = 1


class Symlink(File):
    ftype = "l"
    default_links_cnt = 1
