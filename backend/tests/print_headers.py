import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_print_headers(async_client: AsyncClient, headers: dict):
    print("HEADERS:", headers)

