"""Entry point: python -m scholar_mcp"""
import atexit
from .server import main, init_shared_state, get_state

# Initialize shared state (PG connection pool + ID resolver cache)
# This is a one-time cost that benefits all subsequent tool calls
init_shared_state()

# Register cleanup hook to close connection pool on exit
atexit.register(lambda: get_state() and get_state().close())

main()
