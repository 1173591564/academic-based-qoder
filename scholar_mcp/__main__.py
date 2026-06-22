"""Entry point: python -m scholar_mcp"""
from .server import main, init_shared_state

# Initialize shared state (PG connection pool + ID resolver cache)
# This is a one-time cost that benefits all subsequent tool calls
init_shared_state()

main()
