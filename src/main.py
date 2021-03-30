import gc
import machine
import network
import ntptime
import uasyncio
import ubinascii
import ujson
import utils
import dfplayer

__debug = True
__hour = 7
__minute = 15

sta_if = network.WLAN(network.STA_IF)
ap_if = network.WLAN(network.AP_IF)

button_1 = utils.Button(12)
neopixel_rgb = utils.RGB(13, 4)

audio = dfplayer.SimpleDFPlayerMini(1, 0, 1)

loop = uasyncio.get_event_loop()
network_updated = uasyncio.Event()
time_updated = uasyncio.Event()
volume_lock = uasyncio.Lock()

def main():
    audio.suspend()
    loop = uasyncio.get_event_loop()
    loop.create_task(network_coro())
    loop.create_task(alarm_time_coro())
    loop.run_forever()

def status():
    return {'network' : {'ip': network.WLAN(network.STA_IF).ifconfig()[0], 'connected': network.WLAN(network.STA_IF).isconnected()}, 'time': utils.cettime()}

async def update_time_coro():
    try:
        if __debug:
            print('update_time_coro: started')
        while True:
            try:
                ntptime.settime()
            except OSError:
                continue
            if __debug:
                print('update_time_coro: time updated')
            time_updated.set()
            gc.collect()
            await uasyncio.sleep(3600)
    except uasyncio.CancelledError:
        if __debug:
            print('update_time_coro: stopped')
        pass

async def alarm_time_coro():
    if __debug:
        print('alarm_time_coro: started')
        print('alarm_time_coro: waiting for time update')
    await time_updated.wait()
    while True:
        now = utils.cettime()
        if now[6] < 5 and now[3] == __hour and now[4] == __minute:
            loop.create_task(alarm_button_coro(loop.create_task(alarm_audio_coro()), loop.create_task(alarm_light_coro())))
            await uasyncio.sleep(60)
        await uasyncio.sleep(5)

async def alarm_button_coro(audio_coro, light_coro):
    if __debug:
        print('alarm_button_coro: started')
    while True:
        if button_1.pressed():
            audio_coro.cancel()
            light_coro.cancel()
            if __debug:
                print('alarm_button_coro: stopped')
            break
        await uasyncio.sleep(.01)

async def alarm_audio_coro():
    try:
        if __debug:
            print('alarm_audio_coro: started')
        audio.resume()
        audio.play()
        if __debug:
            print('alarm_audio_coro: playback started')
        while True:
            async with volume_lock:
                audio.inc_vol()
            if __debug:
                print('alarm_audio_coro: volume increased to {volume}'.format(volume=audio.get_vol()))
            await uasyncio.sleep(10)
    except uasyncio.CancelledError:
        async with volume_lock:
            audio.set_vol(0)
            if __debug:
                print('alarm_audio_coro: volume set to {volume}'.format(volume=audio.get_vol()))
        audio.suspend()
        if __debug:
            print('alarm_audio_coro: playback stopped')
        if __debug:
            print('alarm_audio_coro: stopped')

async def alarm_light_coro():
    try:
        if __debug:
            print('alarm_light_coro: started')
        while True:
            async with volume_lock:
                volume = audio.get_vol()
            if volume < 15:
                color = 'green'
            else:
                color = 'red'
            fade_time = (10.0 / 2 - volume * 0.1) / 2
            if __debug:
                print('alarm_light_coro: fade_time = {fade_time}'.format(fade_time=fade_time))
            await neopixel_rgb.fade_in(color, fade_time)
            await neopixel_rgb.fade_out(color, fade_time)
    except uasyncio.CancelledError:
        await neopixel_rgb.off()
        if __debug:
            print('alarm_light_coro: stopped')

async def network_coro():
    if __debug:
        print('network_coro: started')
    sta_if.active(False)
    ap_if.active(True)
    ap_if.config(essid='wecker_{id}'.format(id=ubinascii.hexlify(machine.unique_id()).decode()), channel=6, authmode=4, password=ubinascii.hexlify(machine.unique_id()).decode())
    if ap_if.active():
        loop.create_task(status_server())
        loop.create_task(config_server())
    while True:
        station_found = False
        try:
            with open('wifi.json', 'rb') as f:
                config = ujson.loads(f.read())
            if __debug:
                print('network_coro: wifi configuration found')
        except OSError:
            if __debug:
                print('network_coro: wifi configuration not found')
                print('network_coro: waiting for network update')
            await network_updated.wait()
            network_updated.clear()
            continue
        sta_if.active(True)
        for station in sta_if.scan():
            if config['ssid'].encode() in station:
                if __debug:
                    print('network_coro: station found')
                station_found = True
        if station_found:
            if __debug:
                print('network_coro: connecting to {ssid}'.format(ssid=config['ssid']))
            sta_if.connect(config['ssid'], config['psk'])
            while not sta_if.isconnected():
                await uasyncio.sleep(.01)
            if __debug:
                print('network_coro: connected to {ssid}'.format(ssid=config['ssid']))
                print('network_coro: got ip address {ip}'.format(ip=sta_if.ifconfig()[0]))
            ntp_coro = loop.create_task(update_time_coro())
            while sta_if.isconnected():
                if network_updated.is_set():
                    sta_if.disconnect()
                    network_updated.clear()
                await uasyncio.sleep(.5)
            if __debug:
                print('network_coro: connection to {ssid} lost'.format(ssid=config['ssid']))
            ntp_coro.cancel()
            continue
        sta_if.active(False)

async def status_handler(creader, cwriter):
    if __debug:
        print('status_handler: connection established by {peer}'.format(peer=creader.get_extra_info('peername')))
    cwriter.write(ujson.dumps(status()))
    await cwriter.drain()
    cwriter.close()
    await cwriter.wait_closed()
    await uasyncio.sleep(.01)

async def status_server():
    if __debug:
        print('status_server: started on port 5000')
    while True:
        await uasyncio.start_server(status_handler, '0.0.0.0', 5000)
        while True:
            await uasyncio.sleep(.01)

async def config_handler(creader, cwriter):
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

async def config_server():
    if __debug:
        print('config_server: started on port 6000')
    while True:
        await uasyncio.start_server(config_handler, '0.0.0.0', 6000)
        while True:
            await uasyncio.sleep(.01)


if __name__ == '__main__':
    main()