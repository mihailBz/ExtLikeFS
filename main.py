from device import StorageDevice
from driver import Driver
from file_system import FileSystem

Byte = int
Address = int

def main():
    block_size: Byte = 4096
    disk_size: Byte = block_size * 10

    inodes_number = 20

    storage_device = StorageDevice(disk_size, 'storage', clear=True)
    driver = Driver(storage_device)
    file_system = FileSystem(driver, block_size, inodes_number)
    file_system.get_free_blocks(1)



if __name__ == '__main__':
    main()