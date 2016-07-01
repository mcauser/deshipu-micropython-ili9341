import time


class SSD1606:
    def __init__(self, width, height, spi, cs, dc, rst, bu):
        """
from machine import Pin, SPI
import ssd1606
spi = SPI(miso=Pin(12), mosi=Pin(13, Pin.OUT), sck=Pin(14, Pin.OUT))
display = ssd1606.SSD1606(172, 72, spi, Pin(4), Pin(5), Pin(2), Pin(15))
        """
        self.width = width
        self.height = height
        self.spi = spi
        self.cs = cs
        self.dc = dc
        self.rst = rst
        self.bu = bu
        self.cs.init(self.cs.OUT, value=1)
        self.dc.init(self.dc.OUT, value=0)
        self.rst.init(self.rst.OUT, value=0)
        self.bu.init(self.bu.IN)
        self.buffer = bytearray(self.height * self.width // 4)
        self.reset()
        self.init()

    def _data(self, data):
        self.cs.high()
        self.dc.high()
        self.cs.low()
        self.spi.write(data)
        self.cs.high()

    def _command(self, command, data=None):
        self.cs.high()
        self.dc.low()
        self.cs.low()
        self.spi.write(bytearray([command]))
        self.cs.high()
        if data is not None:
            self._data(data)

    def _wait_busy(self):
        while self.bu.value():
            time.sleep_ms(10)

    def sleep(self, sleep):
        self._command(0x10, bool(sleep))

    def init(self):
        for command, data in (
            (0x10, b'\x00'), # Exit deep sleep mode
            (0x11, b'\x03'), # Data enter mode
            (0x21, b'\x03'), # Display update options
            (0xf0, b'\x1f'), # Booster feedback used, in page 37
            (0x2c, b'\xa0'), # VCOM
            (0x3c, b'\x63'), # Board
            (0x22, b'\xc4'), # Display update sequence option, in page 33
            # Enable sequence: clk -> CP -> LUT -> initial display -> pattern
            (0x32,  b'\x00\x00\x00\x55\x00\x00\x55\x55'
                    b'\x00\x55\x55\x55\x55\x55\x55\x55'
                    b'\x55\xAA\x55\x55\xAA\xAA\xAA\xAA'
                    b'\x05\x05\x05\x05\x15\x15\x15\x15'
                    b'\x01\x01\x01\x01\x00\x00\x00\x00'
                    b'\x00\x00\x00\x00\x00\x00\x00\x00'
                    b'\x00\x00\x00\x00\x00\x00\x00\x00'
                    b'\x00\x00\x00\x00\x00\x00\x00\x00'
                    b'\x00\x00\x00\x00\x00\x00\x00\x00'
                    b'\x00\x00\x00\x00\x00\x00\x00\x00'
                    b'\x34\x32\xF1\x74\x14\x00\x00\x00'
                    b'\x00\x00'), # Write LUT
        ):
            self._command(command, data)

    def reset(self):
        self.rst.low()
        time.sleep_ms(10)
        self.rst.high()
        time.sleep_ms(10)

    def show(self):
        self._command(0x44, bytearray([0, self.height // 4 - 1])), # Set RAM y address start/end in page 36
        self._command(0x45, bytearray([0, self.width - 1])), # Set RAM y address start/end in page 37
        self._command(0x4e, b'\x00'), # Set RAM y address count to 0
        self._command(0x4f, b'\x00'), # Set RAM x address count to 0
        self._command(0x24, self.buffer) # Write data
        self._command(0x20) # Update display
        self._wait_busy()

    def pixel(self, x, y, color):
        if not 0 <= x < self.width or not 0 <= y < self.height:
            return
        if not 0 <= color <= 3:
            raise ValueError("invalid color")
        row, bit = divmod(y, 4)
        bit = 3 - bit
        mask = 0x03 << (bit * 2)
        data = color << (bit * 2)
        address = row + (self.width - x - 1) * self.height // 4
        self.buffer[address] &= ~mask
        self.buffer[address] |= data

    def fill(self, color):
        color &= 0x03
        data = color | color << 2 | color << 4 | color << 6
        for i in range(self.height * self.width // 4):
            self.buffer[i] = data

