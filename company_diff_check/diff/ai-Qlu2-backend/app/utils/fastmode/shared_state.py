# Shared state for fastmode module
# This prevents circular imports between fast.py and suggestions.py

ASYNC_TASKS = {}
