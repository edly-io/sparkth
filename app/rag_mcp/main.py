"""RAG MCP server entry point."""

import argparse

from app.rag_mcp.server import mcp


def main() -> None:
    """Run the RAG MCP server."""
    parser = argparse.ArgumentParser(description="RAG Metadata MCP Server")
    parser.add_argument("--host", default="0.0.0.0", help="Server host")
    parser.add_argument("--port", type=int, default=7728, help="Server port")

    args = parser.parse_args()

    mcp.run(transport="http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
