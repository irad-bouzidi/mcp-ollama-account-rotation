import pytest

from app.server import create_server


@pytest.mark.asyncio
async def test_server_creation():
    server = await create_server("tests/fixtures/test_config.yaml")
    assert server is not None


def test_server_name():
    import anyio

    server = anyio.run(create_server, "tests/fixtures/test_config.yaml")
    assert server.name == "ollama-router-mcp"


@pytest.mark.asyncio
async def test_server_list_tools():
    server = await create_server("tests/fixtures/test_config.yaml")
    tools_fn = server.list_tools()
    assert callable(tools_fn)


@pytest.mark.asyncio
async def test_server_list_resources():
    server = await create_server("tests/fixtures/test_config.yaml")
    resources_fn = server.list_resources()
    assert callable(resources_fn)
