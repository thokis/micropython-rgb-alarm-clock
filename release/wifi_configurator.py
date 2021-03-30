import asyncio
import getpass

async def main():
    ssid = input('SSID: ')
    psk = getpass.getpass()
    sreader, swriter = await asyncio.open_connection('192.168.4.1', 6000)
    swriter.write(int(len(ssid)).to_bytes(4, 'little'))
    swriter.write(int(len(psk)).to_bytes(4, 'little'))
    swriter.write(ssid.encode())
    swriter.write(psk.encode())
    await swriter.drain()
    swriter.close()
    await swriter.wait_closed()
    await asyncio.sleep(0.02)

if __name__ == '__main__':
    asyncio.run(main())
