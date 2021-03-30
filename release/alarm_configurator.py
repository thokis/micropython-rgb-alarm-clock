import asyncio
import getpass

async def main():
    while True:
        try:
            hour = int(input('Hour: '))
            minute = int(input('Minute: '))
            break     
        except ValueError:
            print('try again')
            continue
    sreader, swriter = await asyncio.open_connection('192.168.4.1', 7000)
    swriter.write(hour.to_bytes(4, 'little'))
    swriter.write(minute.to_bytes(4, 'little'))
    await swriter.drain()
    swriter.close()
    await swriter.wait_closed()
    await asyncio.sleep(0.02)

if __name__ == '__main__':
    asyncio.run(main())
