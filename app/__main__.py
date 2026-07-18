import argparse

import anyio

from app.server import create_server


def main() -> None:
    parser = argparse.ArgumentParser(description="Ollama Account Rotation MCP Server")
    parser.add_argument(
        "-c",
        "--config",
        default="data/config.yaml",
        help="Path to configuration file (default: data/config.yaml)",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for SSE transport (default: 8000)",
    )
    args = parser.parse_args()

    async def _run() -> None:
        server = await create_server(args.config)
        if args.transport == "sse":
            import uvicorn
            from mcp.server.sse import SseServerTransport
            from starlette.applications import Starlette
            from starlette.routing import Mount, Route

            sse = SseServerTransport("/messages")

            async def handle_sse(request):  # type: ignore[no-untyped-def]
                async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
                    await server.run(streams[0], streams[1], server.create_initialization_options())

            from starlette.responses import JSONResponse

            async def health(request):
                return JSONResponse({"status": "ok"})

            app = Starlette(
                routes=[
                    Route("/health", endpoint=health),
                    Route("/sse", endpoint=handle_sse),
                    Mount("/messages", app=sse.handle_post_message),
                ]
            )
            cfg = uvicorn.Config(app, host="0.0.0.0", port=args.port, loop="asyncio")
            srv = uvicorn.Server(cfg)
            await srv.serve()
        else:
            from mcp.server.stdio import stdio_server

            async with stdio_server() as (read_stream, write_stream):
                await server.run(read_stream, write_stream, server.create_initialization_options())

    try:
        anyio.run(_run)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
