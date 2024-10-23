from pathlib import Path

import serial
from bit_stream_flasher import BitStreamTransferProtocol, BitStreamTransmitter

if __name__ == "__main__":
    port_fid = "/dev/cu.usbmodem1103"
    bit_file = "./binfile.bin"
    with serial.Serial(port_fid) as port:
        p = BitStreamTransferProtocol(port)
        t = BitStreamTransmitter(p)
        t.upload_bitstream_to(Path(bit_file), 0x03)

