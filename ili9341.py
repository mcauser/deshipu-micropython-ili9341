import time
import ustruct
import framebuf


def color565(r, g, b):
    return (r & 0xf8) << 8 | (g & 0xfc) << 3 | b >> 3


def chunk_bytes(data, chunk, buffer=None):
    if buffer is None:
        buffer = bytearray(chunk)
    cursor = 0
    for byte in data:
        buffer[cursor] = byte
        cursor += 1
        if cursor >= chunk:
            yield buffer
            cursor = 0
    yield buffer[0:cursor]


def color_bytes(color, count):
    data = ustruct.pack(">H", color)
    for i in range(count):
        yield from iter(data)


class ILI9341:
    """
    A simple driver for the ILI9341/ILI9340-based displays.


    >>> import ili9341
    >>> from machine import Pin, SPI
    >>> spi = SPI(miso=Pin(12), mosi=Pin(13, Pin.OUT), sck=Pin(14, Pin.OUT))
    >>> display = ili9341.ILI9341(spi, cs=Pin(4), dc=Pin(5), rst=Pin(15))
    >>> display.fill(ili9341.color565(0xff, 0x11, 0x22))
    >>> display.pixel(120, 160, 0)
    """

    width = 240
    height = 320
    rate = 100 * 1024 * 1024

    def __init__(self, spi, cs, dc, rst):
        self.spi = spi
        self.cs = cs
        self.dc = dc
        self.rst = rst
        self.cs.init(self.cs.OUT, value=1)
        self.dc.init(self.dc.OUT, value=0)
        self.rst.init(self.rst.OUT, value=0)
        self.reset()
        self.init()
        self._scroll = 0

    def init(self):
        for command, data in (
            (0xef, b'\x03\x80\x02'),
            (0xcf, b'\x00\xc1\x30'),
            (0xed, b'\x64\x03\x12\x81'),
            (0xe8, b'\x85\x00\x78'),
            (0xcb, b'\x39\x2c\x00\x34\x02'),
            (0xf7, b'\x20'),
            (0xea, b'\x00\x00'),
            (0xc0, b'\x23'),  # Power Control 1, VRH[5:0]
            (0xc1, b'\x10'),  # Power Control 2, SAP[2:0], BT[3:0]
            (0xc5, b'\x3e\x28'),  # VCM Control 1
            (0xc7, b'\x86'),  # VCM Control 2
            (0x36, b'\x48'),  # Memory Access Control
            (0x3a, b'\x55'),  # Pixel Format
            (0xb1, b'\x00\x18'),  # FRMCTR1
            (0xb6, b'\x08\x82\x27'),  # Display Function Control
            (0xf2, b'\x00'),  # 3Gamma Function Disable
            (0x26, b'\x01'),  # Gamma Curve Selected
            (0xe0,  # Set Gamma
             b'\x0f\x31\x2b\x0c\x0e\x08\x4e\xf1\x37\x07\x10\x03\x0e\x09\x00'),
            (0xe1,  # Set Gamma
             b'\x00\x0e\x14\x03\x11\x07\x31\xc1\x48\x08\x0f\x0c\x31\x36\x0f'),
        ):
            self._write_command(command)
            self._write_data(data)
        self._write_command(0x11)  # Exist Sleep
        time.sleep_ms(120)
        self._write_command(0x29)  # Display On

    def reset(self):
        self.rst.high()
        time.sleep_ms(5)
        self.rst.low()
        time.sleep_ms(20)
        self.rst.high()
        time.sleep_ms(150)

    def _write_command(self, command):
        self.spi.init(baudrate=self.rate, polarity=0, phase=0)
        self.cs.high()
        self.dc.low()
        self.cs.low()
        self.spi.write(bytearray([command]))
        self.cs.high()

    def _write_data(self, data):
        self.spi.init(baudrate=self.rate, polarity=0, phase=0)
        self.cs.high()
        self.dc.high()
        self.cs.low()
        self.spi.write(data)
        self.cs.high()

    def _write_block(self, x0, y0, x1, y1, data):
        self._write_command(0x2a)  # CASET
        self._write_data(ustruct.pack(">HH", x0, x1))
        self._write_command(0x2b)  # PASET

        self._write_data(ustruct.pack(">HH", y0, y1))
        self._write_command(0x2c)  # Ram Write
        self._write_data(data)

    def pixel(self, x, y, color):
        if not 0 <= x < self.width or not 0 <= y < self.height:
            return
        self._write_block(x, y, x, y, ustruct.pack(">H", color))

    def fill_rectangle(self, x, y, w, h, color):
        x = min(self.width - 1, max(0, x))
        y = min(self.height - 1, max(0, y))
        w = min(self.width - x, max(1, w))
        h = min(self.height - y, max(1, h))
        buffer = bytearray(1024)
        self._write_block(x, y, x + w - 1, y + h - 1, b'')
        for chunk in chunk_bytes(color_bytes(color, w*h), 1024, buffer):
            self._write_data(chunk)

    def fill(self, color):
        self.fill_rectangle(0, 0, self.width, self.height, color)

    def char(self, char, x, y, color=0xffff, background=0x0000):
        buffer = bytearray(8)
        framebuffer = framebuf.FrameBuffer1(buffer, 8, 8)
        framebuffer.text(char, 0, 0)
        color = ustruct.pack(">H", color)
        background = ustruct.pack(">H", background)
        data = bytearray(2 * 8 * 8)
        for c, byte in enumerate(buffer):
            for r in range(8):
                if byte & (1 << r):
                    data[r * 8 * 2 + c * 2] = color[0]
                    data[r * 8 * 2 + c * 2 + 1] = color[1]
                else:
                    data[r * 8 * 2 + c * 2] = background[0]
                    data[r * 8 * 2 + c * 2 + 1] = background[1]
        self._write_block(x, y, x + 7, y + 7, data)

    def text(self, text, x, y, color=0xffff, background=0x0000, wrap=None,
             vwrap=None, clear_eol=False):
        if wrap is None:
            wrap = self.width - 8
        if vwrap is None:
            vwrap = self.height - 8
        tx = x
        ty = y

        def new_line():
            nonlocal tx, ty

            tx = x
            ty += 8
            if ty >= vwrap:
                ty = y

        for char in text:
            if char == '\n':
                if clear_eol and tx < wrap:
                    self.fill_rectangle(tx, ty, wrap - tx + 7, 8, background)
                new_line()
            else:
                if tx >= wrap:
                    new_line()
                self.char(char, tx, ty, color, background)
                tx += 8
        if clear_eol and tx < wrap:
            self.fill_rectangle(tx, ty, wrap - tx + 7, 8, background)

    def scroll(self, dy=None):
        if dy is None:
            return self._scroll
        self._scroll = (self._scroll + dy) % self.height
        self._write_command(0x37)  # Vertical Scroll Address
        self._write_data(ustruct.pack('>H', self._scroll))
