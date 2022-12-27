Byte = int
Address = int


class StorageDevice:
    def __init__(self, file_path: str, size: Byte, block_size: Byte = 4096) -> None:
        assert size % block_size == 0
        self.storage_path = file_path
        self._size = size
        self._block_size = block_size
        with open(file_path, 'r+') as f:
            f.truncate()
        # self.inodes_number = inodes_number
        # self.bitmap = [0 for _ in size // block_size]

    @property
    def size(self):
        return self._size

    @property
    def block_size(self):
        return self._block_size

    def write(self, data: bytes, address: Address):
        with open(self.storage_path, 'ab+') as storage:
            storage.seek(address)
            storage.write(data)



class Sector:
    def __init__(self, offset: Address, size) -> None:
        self._offset = offset
        self._size = size

class Bitmap(Sector):
    def __init__(self, offset: Address, size: Byte) -> None:
        self._value = ['0']*size
        super().__init__(offset, size)
    
    @property
    def value(self):
        return self._value

class InodesSector(Sector):
    pass

class DataSector(Sector):
    pass

class Inode:
    size: Byte = 256


class FileSystem:
    def __init__(self, storage_device: StorageDevice, inodes_number: Byte) -> None:
        blocks_number = (
            storage_device.size // storage_device.block_size
            - inodes_number // (storage_device.size / Inode.size)
        )
        bitmap_blocks_number = 0
        while bitmap_blocks_number * storage_device.block_size < blocks_number:
            bitmap_blocks_number += 1
        blocks_number -= bitmap_blocks_number

        inodes_sector_size = inodes_number * Inode.size
        
        self._Bitmap = Bitmap(offset=0, size=int(blocks_number))
        storage_device.write(''.join(self._Bitmap.value).encode('ascii'), 0)
    

def main():
    disk_size = 4096*10
    inodes_number = 20

    SD = StorageDevice(
        file_path='storage.txt',
        size=disk_size
    )
    FS = FileSystem(storage_device=SD, inodes_number=inodes_number)



        
if __name__ == "__main__":
    main()