"""CB-CMCP-001 service package.

Houses curriculum-aware MCP services (artifact state machine, validators,
generators, etc.). Pure-logic modules in this package must not perform DB
or network I/O so they can be reused across worker, API, and test contexts.
"""
