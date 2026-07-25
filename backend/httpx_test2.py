import asyncio
import httpx
from config import settings

async def main():
    print("URL:", settings.N8N_WEBHOOK_URL)
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(settings.N8N_WEBHOOK_URL, json={"action": "test"})
            print(response.status_code)
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(main())
