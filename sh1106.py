import framebuf
import time


_SET_PAGE_ADDRESS = const(0xB0)
_DISPLAY_OFF = const(0xAE)
_DISPLAY_ON = const(0xAF)
_LOW_COLUMN_ADDRESS = const(0x00)
_HIGH_COLUMN_ADDRESS = const(0x10)
_START_LINE_ADDRESS = const(0x40)
_SET_CONTRAST_CTRL_REG = const(0x81)
_SET_NORMAL_DISPLAY = const(0xA6) # normal/inverse


class SH1106:
    width = 128
    height = 64

    def __init__(self, spi, dc, rst, cs):
        self.spi = spi
        self.cs = cs
        self.dc = dc
        self.rst = rst
        self.cs.init(self.cs.OUT, value=1)
        self.dc.init(self.dc.OUT, value=0)
        self.rst.init(self.rst.OUT, value=1)
        self._buffer = bytearray(self.height // 8 * self.width)
        self._framebuf = framebuf.FrameBuffer1(
            self._buffer, self.width, self.height)
        self.reset()

    def reset(self):
        self.rst.low()
        time.sleep_ms(50)
        self.rst.high()
        time.sleep_ms(50)

    def _data(self, data):
        self.dc.high()
        self.cs.low()
        self.spi.write(data)
        self.cs.high()

    def _write(self, command, data=None):
        self.dc.low()
        self.cs.low()
        self.spi.write(bytearray([command]))
        self.cs.high()
        if data:
            self._data(data)

    def vscroll(self, dy):
        self._write(_START_LINE_ADDRESS | dy & 0x3f)

    def inverse(self, value):
        self._write(_SET_NORMAL_DISPLAY | bool(value))

    def contrast(self, value):
        self._write(_SET_CONTRAST_CTRL_REG, bytearray([value]))

    def sleep(self, value):
        self._write(_DISPLAY_OFF | (not value))

    def fill(self, col):
        self._framebuf.fill(col)

    def pixel(self, x, y, col):
        self._framebuf.pixel(x, y, col)

    def scroll(self, dx, dy):
        self._framebuf.scroll(dx, dy)

    def text(self, string, x, y, col=1):
        self._framebuf.text(string, x, y, col)

    def show(self):
        for page in range(self.height // 8):
            self._write(_SET_PAGE_ADDRESS | page)
            self._write(_LOW_COLUMN_ADDRESS | 2)
            self._write(_HIGH_COLUMN_ADDRESS | 0)
            self._data(self._buffer[
                self.width * page:self.width * page + self.width
            ])
