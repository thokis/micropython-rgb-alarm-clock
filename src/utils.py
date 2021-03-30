import machine
import uasyncio
import neopixel
import utime

def cettime():
    year = utime.localtime()[0]       #get current year
    HHMarch   = utime.mktime((year,3 ,(31-(int(5*year/4+4))%7),1,0,0,0,0,0)) #Time of March change to CEST
    HHOctober = utime.mktime((year,10,(31-(int(5*year/4+1))%7),1,0,0,0,0,0)) #Time of October change to CET
    now=utime.time()
    if now < HHMarch :               # we are before last sunday of march
        cet=utime.localtime(now+3600) # CET:  UTC+1H
    elif now < HHOctober :           # we are before last sunday of october
        cet=utime.localtime(now+7200) # CEST: UTC+2H
    else:                            # we are after last sunday of october
        cet=utime.localtime(now+3600) # CET:  UTC+1H
    return(cet)

class Button:

    def __init__(self, pin):
        self.__button = machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_UP)

    def pressed(self):
        return not self.__button.value()

class RGB:

    def __init__(self, pin, quantity):
        self.__rgb = neopixel.NeoPixel(machine.Pin(pin), quantity)
        self.__color = {'red': 0, 'green': 0, 'blue': 0}
        for i in range(self.__rgb.n):
            self.__rgb[i] = self.__generate_color()
        self.__rgb.write()

    async def off(self):
        for color in self.__color:
            self.__color[color] = 0
        for i in range(self.__rgb.n):
            self.__rgb[i] = self.__generate_color()
        self.__rgb.write()
        await uasyncio.sleep(0.01)

    def __generate_color(self):
        return (self.__color['red'], self.__color['green'], self.__color['blue'])

    async def fade_in(self, color, fade_time):
        for step in range(255 - self.__color[color]):
            self.__color[color] += 1
            for i in range(self.__rgb.n):
                self.__rgb[i] = self.__generate_color()
            self.__rgb.write()
        await uasyncio.sleep(fade_time)

    async def fade_out(self, color, fade_time):
        for step in range(self.__color[color]):
            self.__color[color] -= 1
            for i in range(self.__rgb.n):
                self.__rgb[i] = self.__generate_color()
            self.__rgb.write()
        await uasyncio.sleep(fade_time)
