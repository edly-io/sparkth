import argparse

from app.mcp.canvas.tools import *  # noqa
from app.mcp.mode import TransportMode
from app.mcp.openedx.tools import *  # noqa
from app.mcp.server import mcp


def run_stdio():
    mcp.run()


def run_http(host, port):
    mcp.run(transport="http", host=host, port=port)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--transport",
        default="http",
        choices=[mode.value for mode in TransportMode],
        help="MCP server transport mode",
    )
    parser.add_argument("--host", default="0.0.0.0", help="MCP server host")
    parser.add_argument("--port", type=int, default=7727, help="MCP server port")

    args = parser.parse_args()
    transport_mode = TransportMode(args.transport)

    if transport_mode == TransportMode.STDIO:
        run_stdio()
    else:
        run_http(args.host, args.port)


if __name__ == "__main__":
    main()
