"""SSH wrappers.

- run_show_running_config(): One-shot exec for batch collection (uses asyncssh).
- open_interactive(): Async context manager returning a PTY process for terminal UI.

Multi-vendor "show running-config" command is mapped from device.vendor.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import AsyncIterator, Tuple

import asyncssh

log = logging.getLogger("ssh")

VENDOR_SHOW_CMD = {
    "cisco_ios":      "terminal length 0\nshow running-config",
    "cisco_xe":       "terminal length 0\nshow running-config",
    "cisco_nxos":     "terminal length 0\nshow running-config",
    "cisco_xr":       "terminal length 0\nshow running-config",
    "arista_eos":     "terminal length 0\nshow running-config",
    "juniper_junos":  "set cli screen-length 0\nshow configuration | display set",
    "linux":          "cat /etc/network/interfaces 2>/dev/null || nmcli connection show",
}


async def run_show_running_config(
    host: str, port: int, username: str, password: str, vendor: str, timeout: int = 30
) -> str:
    """Connect, request show running-config, return the captured config."""
    cmd_seq = VENDOR_SHOW_CMD.get(vendor, "show running-config")
    log.info("collecting config host=%s vendor=%s", host, vendor)

    async with asyncssh.connect(
        host,
        port=port,
        username=username,
        password=password,
        known_hosts=None,            # for production: pin host keys
        connect_timeout=timeout,
    ) as conn:
        # Use interactive shell because some devices reject 'exec'
        proc = await conn.create_process(term_type="vt100", term_size=(200, 5000))
        for line in cmd_seq.split("\n"):
            proc.stdin.write(line + "\n")
        proc.stdin.write("exit\n")
        proc.stdin.write_eof()

        try:
            stdout = await asyncio.wait_for(proc.stdout.read(), timeout=timeout)
        except asyncio.TimeoutError:
            stdout = ""
        return stdout


@contextlib.asynccontextmanager
async def open_interactive(
    host: str, port: int, username: str, password: str
) -> AsyncIterator[Tuple[asyncssh.SSHClientProcess, asyncssh.SSHClientConnection]]:
    """Yield (process, conn) of a PTY-attached shell for the WebSocket terminal."""
    conn = await asyncssh.connect(
        host, port=port, username=username, password=password,
        known_hosts=None, keepalive_interval=15,
    )
    try:
        process = await conn.create_process(term_type="xterm-256color", term_size=(120, 40))
        yield process, conn
    finally:
        with contextlib.suppress(Exception):
            conn.close()
            await conn.wait_closed()
