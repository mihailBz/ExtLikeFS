class FileSystemException(Exception):
    pass


class OutOfInodes(FileSystemException):
    pass


class InvalidPath(FileSystemException):
    pass


class FileDoesNotExist(FileSystemException):
    pass


class FileAlreadyExists(FileSystemException):
    pass


class OutOfBlocks(FileSystemException):
    pass


class InvalidSize(FileSystemException):
    pass


class CannotRemoveDirectory(FileSystemException):
    pass


class TooLongSymlink(FileSystemException):
    pass


class TooManyFilesOpen(FileSystemException):
    pass


class WrongFileDescriptorNumber(FileSystemException):
    pass


class DirectoryLinkException(FileSystemException):
    pass


class InvalidInput(FileSystemException):
    pass


class CannotUnlinkOpenFile(FileSystemException):
    pass
