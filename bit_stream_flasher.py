import math
from enum import Enum
from pathlib import Path


class ControlChars(Enum):
    ACK = b'\06'
    NAK = b'\x15'
    SOH = b'\x01'  # start of header
    EOT = b'\x04'  # end of transmission
    CAN = b'\x18'  # cancel
    C = b'C'    # latin capital C
    START_TRANSMISSION = b'1'


class Packet:
    MAX_SIZE = 256
    """The packet structure is inspired by xmodem, but second byte denotes
    payload length instead of block number in two's complement.
    """
    def __init__(self, block_number: int, payload: bytearray | list[int]):
        self._block_number = self.int_to_bytes(block_number, 2)
        self._start_of_header = ControlChars.SOH.value
        if not isinstance(payload, bytearray):
            self._payload = bytearray(payload)
        else:
            self._payload = payload

    @property
    def block_number(self):
        raise PermissionError('Block number is write-only')

    @block_number.setter
    def block_number(self, value: int) -> None:
        self._block_number = self.int_to_bytes(value, 2)

    @staticmethod
    def int_to_bytes(value, length):
        return bytes([(value >> i*8) & 0xff for i in reversed(range(length))])

    @property
    def _payload_length(self):
        return self.int_to_bytes(len(self._payload), 2)

    @property
    def _check_sum(self):
        return self.int_to_bytes(sum(self._payload) & 0xff, 1)

    def as_bytearray(self) -> bytearray:
        packet = bytes().join((
            self._start_of_header,
            self._block_number,
            self._payload_length,
            self._payload,
            self._check_sum
        ))

        return packet


class BitStreamTransferProtocol:

    def __init__(self, serial_port):
        self._sp = serial_port
        self._crc_mode = None

    def _make_bytes(self, data: bytearray | list[int] | list[bytes] | list[ControlChars] | ControlChars | int) -> bytes:
        if isinstance(data, bytearray):
            return bytes(data)
        if isinstance(data, list):
            if len(data) == 0:
                return bytes()
            elif isinstance(data[0], ControlChars):
                return self._make_bytes([v.value for v in data])
            elif isinstance(data[0], int):
                return bytes(data)
            elif isinstance(data[0], bytes):
                return bytes().join(data)
        if isinstance(data, int) or isinstance(data, ControlChars):
            return self._make_bytes([data])
        else:
            raise ValueError(f'Unsupported data type: {type(data)}')

    def _write(self, data: bytearray | list[ControlChars] | ControlChars | list[int]):
        data = self._make_bytes(data)
        self._sp.write(data)

    def start_transmission(self) -> None:
        self._write(ControlChars.START_TRANSMISSION)
        self._crc_mode = self._check_crc_mode()

    def _check_crc_mode(self):
        return self._wait_for_chars([ControlChars.C.value, ControlChars.NAK.value])

    def _wait_for_ack(self):
        return self._wait_for_chars([ControlChars.ACK.value,
                                     ControlChars.NAK.value]) == ControlChars.ACK.value

    def stop_transmission(self) -> None:
        self._write(ControlChars.EOT)
        self._sp.read_until(ControlChars.ACK.value)

    def _wait_for_chars(self, chars):
        while True:
            ch = self._sp.read()
            if ch in chars:
                return ch

    def send_packet(self, packet: Packet) -> bool:
        self._sp.write(packet.as_bytearray())
        return self._wait_for_ack()


class BitStreamTransmitter:
    def __init__(self, protocol: BitStreamTransferProtocol):
        self._p = protocol
        self._data = bytearray()
        self._addr_int = 0

    @staticmethod
    def _calc_num_required_packets(file_length: int) -> int:
        return math.floor(file_length / Packet.MAX_SIZE) if file_length % Packet.MAX_SIZE == 0 else math.floor(file_length / Packet.MAX_SIZE) + 1

    @property
    def _num_required_packets_int(self) -> int:
        return self._calc_num_required_packets(len(self._data))

    @property
    def _address(self) -> list[int]:
        return Packet.int_to_bytes(self._addr_int, 4)

    @property
    def _num_required_packets(self) -> list[int]:
        return Packet.int_to_bytes(self._num_required_packets_int, 4)

    def _send_num_packets_and_address(self):
        payload = self._address + self._num_required_packets
        self._p.send_packet(Packet(0x00, payload))

    def _start_transmission(self):
        self._p.start_transmission()

    def _stop_transmission(self):
        self._p.stop_transmission()

    def _send_bitfile_content(self):
        for id in range(self._num_required_packets_int):
            print(f"sending package {id} of {self._num_required_packets_int}")
            self._p.send_packet(Packet(id+1, self._data[id*Packet.MAX_SIZE:(id+1)*Packet.MAX_SIZE]))

    def upload_bitstream_to(self, bitfile: Path, address: int) -> None:
        with open(bitfile, 'rb') as f:
            self._data = f.read()
        self._addr_int = address
        print(f"starting transmission, sending {bitfile.absolute()}")
        self._start_transmission()
        print(f"writing {self._num_required_packets_int} packets to address {self._addr_int}")
        self._send_num_packets_and_address()
        self._send_bitfile_content()
        self._stop_transmission()
        print("done.")



