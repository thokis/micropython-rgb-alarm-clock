import gc
import machine
import network
import ntptime
import uasyncio
import ubinascii
import ujson
import utils
import dfplayer

__hour = 7
__minute = 15

sta_if = network.WLAN(network.STA_IF)
ap_if = network.WLAN(network.AP_IF)

button_1 = utils.Button(12)
neopixel_rgb = utils.RGB(13, 4)

audio = dfplayer.SimpleDFPlayerMini(1, 0, 1)

loop = uasyncio.get_event_loop()
network_updated = uasyncio.Event()
alarm_updated = uasyncio.Event()
time_updated = uasyncio.Event()
volume_lock = uasyncio.Lock()

def main():
    audio.suspend()
    loop = uasyncio.get_event_loop()
    loop.create_task(network_coro())
    loop.create_task(alarm_time_coro())
    loop.run_forever()

def status():
    with open('wifi.json', 'rb') as f:
        wifi = ujson.loads(f.read())
    with open('alarm.json', 'rb') as f:
        alarm = ujson.loads(f.read())
    return {'network' : {'ssid': wifi['ssid'], 'ip': network.WLAN(network.STA_IF).ifconfig()[0], 'connected': network.WLAN(network.STA_IF).isconnected()}, 'time': utils.cettime(), 'alarm' : {'hour': alarm['hour'], 'minute': alarm['minute']}}

async def update_time_coro():
    try:
        while True:
            try:
                ntptime.settime()
            except OSError:
                continue
            time_updated.set()
            gc.collect()
            await uasyncio.sleep(3600)
    except uasyncio.CancelledError:
        pass

async def alarm_time_coro():
    await time_updated.wait()
    alarm = None
    while True:
        try:
            with open('alarm.json', 'rb') as f:
                alarm = ujson.loads(f.read())
            break
        except OSError:
            await alarm_updated.wait()
            alarm_updated.clear()
            continue
    while True:
        if alarm_updated.is_set():
            with open('alarm.json', 'rb') as f:
                alarm = ujson.loads(f.read())
            alarm_updated.clear()
        now = utils.cettime()
        if now[6] < 5 and now[3] == alarm['hour'] and now[4] == alarm['minute']:
            loop.create_task(alarm_button_coro(loop.create_task(alarm_audio_coro()), loop.create_task(alarm_light_coro())))
            await uasyncio.sleep(60)
        await uasyncio.sleep(5)

async def alarm_button_coro(audio_coro, light_coro):
    while True:
        if button_1.pressed():
            audio_coro.cancel()
            light_coro.cancel()
            break
        await uasyncio.sleep(.01)

async def alarm_audio_coro():
    try:
        audio.resume()
        audio.play()
        while True:
            async with volume_lock:
                audio.inc_vol()
            await uasyncio.sleep(10)
    except uasyncio.CancelledError:
        async with volume_lock:
            audio.set_vol(0)
        audio.suspend()

async def alarm_light_coro():
    try:
        while True:
            async with volume_lock:
                volume = audio.get_vol()
            if volume < 15:
                color = 'green'
            else:
                color = 'red'
            fade_time = (10.0 / 2 - volume * 0.1) / 2
            await neopixel_rgb.fade_in(color, fade_time)
            await neopixel_rgb.fade_out(color, fade_time)
    except uasyncio.CancelledError:
        await neopixel_rgb.off()

async def network_coro():
    sta_if.active(False)
    ap_if.active(True)
    ap_if.config(essid='wecker_{id}'.format(id=ubinascii.hexlify(machine.unique_id()).decode()), channel=6, authmode=4, password=ubinascii.hexlify(machine.unique_id()).decode())
    if ap_if.active():
        loop.create_task(status_server())
        loop.create_task(wifi_config_server())
        loop.create_task(alarm_config_server())
    while True:
        station_found = False
        try:
            with open('wifi.json', 'rb') as f:
                config = ujson.loads(f.read())
        except OSError:
            await network_updated.wait()
            network_updated.clear()
            continue
        sta_if.active(True)
        for station in sta_if.scan():
            if config['ssid'].encode() in station:
                station_found = True
        if station_found:
            sta_if.connect(config['ssid'], config['psk'])
            while not sta_if.isconnected():
                await uasyncio.sleep(.01)
            ntp_coro = loop.create_task(update_time_coro())
            while sta_if.isconnected():
                if network_updated.is_set():
                    sta_if.disconnect()
                    network_updated.clear()
                await uasyncio.sleep(.5)
            ntp_coro.cancel()
            continue
        sta_if.active(False)

async def status_handler(creader, cwriter):
    cwriter.write(ujson.dumps(status()))
    await cwriter.drain()
    cwriter.close()
    await cwriter.wait_closed()
    await uasyncio.sleep(.01)

async def status_server():
    while True:
        await uasyncio.start_server(status_handler, '0.0.0.0', 5000)
        while True:
            await uasyncio.sleep(.01)

async def wifi_config_handler(creader, cwriter):
    ssid_len = int().from_bytes(await creader.read(4), 'little')
    psk_len = int().from_bytes(await creader.read(4), 'little')
    b_ssid = await creader.read(ssid_len)
    b_psk = await creader.read(psk_len)
    cwriter.close()
    await cwriter.wait_closed()
    with open('wifi.json', 'wb') as f:
        f.write(ujson.dumps({'ssid' : b_ssid.decode(), 'psk' : b_psk.decode()}))
    await uasyncio.sleep(.01)
    network_updated.set()

async def wifi_config_server():
    while True:
        await uasyncio.start_server(wifi_config_handler, '0.0.0.0', 6000)
        while True:
            await uasyncio.sleep(.01)

async def alarm_config_handler(creader, cwriter):
    hour = int().from_bytes(await creader.read(4), 'little')
    minute = int().from_bytes(await creader.read(4), 'little')
    cwriter.close()
    await cwriter.wait_closed()
    with open('alarm.json', 'wb') as f:
        f.write(ujson.dumps({'hour' : hour, 'minute' : minute}))
    await uasyncio.sleep(.01)
    alarm_updated.set()

async def alarm_config_server():
    while True:
        await uasyncio.start_server(alarm_config_handler, '0.0.0.0', 7000)
        while True:
            await uasyncio.sleep(.01)


if __name__ == '__main__':
    main()