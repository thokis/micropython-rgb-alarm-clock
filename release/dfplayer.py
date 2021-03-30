from machine import UART
from utime import sleep_ms


class SimpleDFPlayerMini:

    def __init__(self, uart_id, volume, mode):
        self._uart = UART(uart_id, baudrate=9600)
        self._send_cmd(0x09, 1)
        self.set_eq(1)
        self._volume = volume
        self.set_vol(self._volume)
        self.set_mode(mode)
        self.pause()

    def _send_cmd(self, cmd, data_low=0, data_high=0):
        self._uart.write(b'\x7E')
        self._uart.write(b'\xFF')
        self._uart.write(b'\x06')
        self._uart.write(bytes([cmd]))
        self._uart.write(b'\x00')
        self._uart.write(bytes([data_high]))
        self._uart.write(bytes([data_low]))
        self._uart.write(b'\xEF')
        sleep_ms(200)

    def next_track(self):
        self._send_cmd(0x01)

    def prev_track(self):
        self._send_cmd(0x02)

    def sel_track(self, track_index):
        self._send_cmd(0x03, track_index)

    def inc_vol(self):
        if self._volume < 20:
            self._volume += 1
            self._send_cmd(0x04)

    def dec_vol(self):
        if self._volume > 0:
            self._volume -= 1
            self._send_cmd(0x05)

    def set_vol(self, volume):
        if volume >= 0 and volume <= 20:
            self._volume = volume
            self._send_cmd(0x06, self._volume)

    def get_vol(self):
        return self._volume

    def set_eq(self, equalizer):
        self._send_cmd(0x07, equalizer)

    def set_mode(self, mode):
        self._send_cmd(0x08, mode)

    def suspend(self):
        self._send_cmd(0x0A)

    def resume(self):
        self._send_cmd(0x09, 1)
        #self._send_cmd(0x0B)

    def reset(self):
        self._send_cmd(0x0C)

    def play(self):
        self._send_cmd(0x0D)

    def pause(self):
        self._send_cmd(0x0E)

    def set_folder(self, folder_index):
        self._send_cmd(0x0F, folder_index)

    def enable_loop(self):
        self._send_cmd(0x11, 1)

    def disable_loop(self):
        self._send_cmd(0x11, 0)
