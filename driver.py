from device import StorageDevice
from bin_serializer import bytes_to_bits, bytes_from_bits

Byte = int
Address = int


class Driver:
    def __init__(self, device: StorageDevice) -> None:
        self._path = device.path
        self._device_size = device.size

    @property
    def path(self) -> str:
        return self._path

    @property
    def device_size(self) -> int:
        return self._device_size

    def write(self, address: Address, data: bytes) -> None:
        with open(self._path, "r+") as storage:
            storage.seek(8 * address)
            storage.write(bytes_to_bits(data))

    def read(self, address: Address, n_bytes: int) -> bytes:
        with open(self._path, "r") as storage:
            storage.seek(8 * address)
            return bytes_from_bits(storage.read(8 * n_bytes))

    def clear(self, address: Address, n_bytes: int) -> None:
        with open(self._path, "r+") as storage:
            storage.seek(8 * address)
            storage.write("0" * 8 * n_bytes)
