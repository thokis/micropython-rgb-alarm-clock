import asyncio
import json

async def main():
    sreader, swriter = await asyncio.open_connection('192.168.4.1', 5000)
    result = await sreader.read()
    print(json.loads(result))
    await asyncio.sleep(0.02)

asyncio.run(main())
