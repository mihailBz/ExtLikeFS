class OutOfInodes(Exception):
    pass


class InvalidPath(Exception):
    pass


class FileDoesNotExist(Exception):
    pass


class FileAlreadyExists(Exception):
    pass


class OutOfBlocks(Exception):
    pass


class InvalidSize(Exception):
    pass


class CannotRemoveDirectory(Exception):
    pass


class TooLongSymlink(Exception):
    pass


class TooManyFilesOpened(Exception):
    pass


class WrongFileDescriptorNumber(Exception):
    pass