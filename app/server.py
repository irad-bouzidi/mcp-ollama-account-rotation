from pathlib import Path

from mcp.server.lowlevel import Server as MCPServer
from mcp.types import Resource, TextContent, Tool
from pydantic import AnyUrl

from app.account_manager import AccountManager
from app.client import OllamaClient
from app.config import load_config
from app.health import HealthChecker
from app.logging import configure_logging, get_logger
from app.models import ChatMessage, ChatRequest, GenerateRequest
from app.router import Router, metrics
from app.storage import StateManager

logger = get_logger(__name__)


async def create_server(config_path: str = "data/config.yaml") -> MCPServer:
    config = load_config(Path(config_path))
    configure_logging(config.logging)

    logger.info("startup", config_path=config_path)

    account_manager = AccountManager(config.accounts_file)
    account_manager.load()

    state_manager = StateManager(config.state_file)
    state_manager.load()

    client = OllamaClient(str(config.ollama_base_url), config.timeouts)

    router = Router(client, account_manager, state_manager, config.retry)
    _ = HealthChecker(client, account_manager, state_manager, config.health)

    server = MCPServer("ollama-router-mcp")

    # === Lifecycle ===
    @server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="chat",
                description="Send a chat completion request to Ollama",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "messages": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "role": {"type": "string"},
                                    "content": {"type": "string"},
                                },
                                "required": ["role", "content"],
                            },
                        },
                        "options": {"type": "object", "default": {}},
                    },
                    "required": ["model", "messages"],
                },
            ),
            Tool(
                name="generate",
                description="Generate text using Ollama",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "prompt": {"type": "string"},
                        "options": {"type": "object", "default": {}},
                    },
                    "required": ["model", "prompt"],
                },
            ),
            Tool(
                name="list_models",
                description="List available models",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="get_account_status",
                description="Get current active account status",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="get_metrics",
                description="Get server metrics",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
        ]

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(name: str, arguments: dict[str, object]) -> list[TextContent]:
        try:
            logger.info("request_received", tool=name)
            if name == "chat":
                messages_list = arguments.get("messages", [])
                assert isinstance(messages_list, list)
                msgs = [ChatMessage(role=m["role"], content=m["content"]) for m in messages_list]
                chat_req = ChatRequest(
                    model=str(arguments["model"]),
                    messages=msgs,
                    options=arguments.get("options", {}),  # type: ignore[arg-type]
                )
                chat_resp = await router.chat(chat_req)
                return [TextContent(type="text", text=chat_resp.message.content)]
            elif name == "generate":
                gen_req = GenerateRequest(
                    model=str(arguments["model"]),
                    prompt=str(arguments["prompt"]),
                    options=arguments.get("options", {}),  # type: ignore[arg-type]
                )
                gen_resp = await router.generate(gen_req)
                return [TextContent(type="text", text=gen_resp.response)]
            elif name == "list_models":
                models = await router.list_models()
                return [TextContent(type="text", text="\n".join(m.name for m in models))]
            elif name == "get_account_status":
                account = account_manager.get_active()
                if account is None:
                    text = "No active account"
                else:
                    state = state_manager.get_account_state(account.id)
                    text = (
                        f"Active: {account.id}\n"
                        f"Email: {account.email}\n"
                        f"Status: {state.status}\n"
                        f"Failures: {state.failure_count}\n"
                        f"Requests: {state.request_count}"
                    )
                return [TextContent(type="text", text=text)]
            elif name == "get_metrics":
                import json

                return [TextContent(type="text", text=json.dumps(metrics.snapshot(), indent=2))]
            else:
                raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            logger.error("tool_error", tool=name, error=str(e))
            raise

    @server.list_resources()  # type: ignore[no-untyped-call,untyped-decorator]
    async def list_resources() -> list[Resource]:
        return [
            Resource(uri=AnyUrl("models://list"), name="Model List", description="List of available models"),
            Resource(uri=AnyUrl("accounts://current"), name="Current Account", description="Active account info"),
            Resource(uri=AnyUrl("accounts://all"), name="All Accounts", description="All accounts and their statuses"),
        ]

    @server.read_resource()  # type: ignore[no-untyped-call,untyped-decorator]
    async def read_resource(uri: AnyUrl) -> str:
        if str(uri) == "models://list":
            models = await router.list_models()
            return "\n".join(m.name for m in models)
        elif str(uri) == "accounts://current":
            account = account_manager.get_active()
            if account is None:
                return "No active account"
            state = state_manager.get_account_state(account.id)
            return (
                f"ID: {account.id}\nEmail: {account.email}\n"
                f"Status: {state.status}\nFailures: {state.failure_count}\n"
                f"Requests: {state.request_count}"
            )
        elif str(uri) == "accounts://all":
            lines = []
            for account in account_manager.get_all():
                state = state_manager.get_account_state(account.id)
                lines.append(
                    f"{account.id}: {state.status} (failures={state.failure_count}, requests={state.request_count})"
                )
            return "\n".join(lines) if lines else "No accounts configured"
        raise ValueError(f"Unknown resource: {uri}")

    return server
