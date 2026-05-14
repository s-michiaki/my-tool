"""Multi-vendor network device config parser.

Extracts a list of `ParsedInterface(name, description, ip)` from running-config
text. Supported vendors:
  - cisco_ios / cisco_xe / cisco_nxos / cisco_xr / arista_eos (IOS-style)
  - juniper_junos (set-style)

The parser is intentionally permissive: it does not need a perfect parse, only
enough to identify interface names and their description strings.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class ParsedInterface:
    name: str
    description: str | None = None
    ip: str | None = None
    enabled: bool = True
    extra: dict = field(default_factory=dict)


# --------------------------------------------------------------------------
# IOS / EOS style
# --------------------------------------------------------------------------
# 'interface GigabitEthernet0/1'
#   description Uplink to core-sw01 Gi1/0/2
#   ip address 10.0.0.1 255.255.255.252
#   shutdown
# !
_IOS_IF_HEADER = re.compile(r"^\s*interface\s+(\S.*?)\s*$", re.IGNORECASE)
_IOS_DESC = re.compile(r"^\s*description\s+(.+?)\s*$", re.IGNORECASE)
_IOS_IP   = re.compile(r"^\s*ip\s+address\s+(\S+)(?:\s+(\S+))?", re.IGNORECASE)
_IOS_SHUT = re.compile(r"^\s*shutdown\s*$", re.IGNORECASE)


def parse_ios(content: str) -> List[ParsedInterface]:
    interfaces: List[ParsedInterface] = []
    current: ParsedInterface | None = None

    for line in content.splitlines():
        # New 'interface XX' section
        m = _IOS_IF_HEADER.match(line)
        if m:
            if current:
                interfaces.append(current)
            current = ParsedInterface(name=m.group(1).strip())
            continue
        # End of section (Cisco's '!' or any non-indented line)
        if current is not None and line and not line.startswith((" ", "\t")):
            interfaces.append(current)
            current = None

        if current is None:
            continue
        m = _IOS_DESC.match(line)
        if m:
            current.description = m.group(1).strip()
            continue
        m = _IOS_IP.match(line)
        if m:
            current.ip = m.group(1).strip()
            continue
        if _IOS_SHUT.match(line):
            current.enabled = False

    if current:
        interfaces.append(current)
    return interfaces


# --------------------------------------------------------------------------
# Junos (set-style)
# --------------------------------------------------------------------------
# set interfaces ge-0/0/0 description "to core-sw01 xe-0/0/1"
# set interfaces ge-0/0/0 unit 0 family inet address 10.0.0.1/30
# set interfaces ge-0/0/0 disable
_JUN_DESC = re.compile(
    r"^set\s+interfaces\s+(\S+)\s+description\s+\"?(.+?)\"?\s*$", re.IGNORECASE
)
_JUN_IP = re.compile(
    r"^set\s+interfaces\s+(\S+)\s+unit\s+\d+\s+family\s+inet\s+address\s+(\S+)",
    re.IGNORECASE,
)
_JUN_DISABLE = re.compile(r"^set\s+interfaces\s+(\S+)\s+disable\s*$", re.IGNORECASE)


def parse_junos(content: str) -> List[ParsedInterface]:
    by_name: dict[str, ParsedInterface] = {}

    def _get(name: str) -> ParsedInterface:
        if name not in by_name:
            by_name[name] = ParsedInterface(name=name)
        return by_name[name]

    for line in content.splitlines():
        m = _JUN_DESC.match(line)
        if m:
            _get(m.group(1)).description = m.group(2).strip()
            continue
        m = _JUN_IP.match(line)
        if m:
            _get(m.group(1)).ip = m.group(2).split("/")[0]
            continue
        m = _JUN_DISABLE.match(line)
        if m:
            _get(m.group(1)).enabled = False

    return list(by_name.values())


# --------------------------------------------------------------------------
# Linux (very simple)
# --------------------------------------------------------------------------
def parse_linux(content: str) -> List[ParsedInterface]:
    return []  # not enough info to be useful here


# --------------------------------------------------------------------------
# Public entrypoint
# --------------------------------------------------------------------------
def parse_config(vendor: str, content: str) -> List[ParsedInterface]:
    v = (vendor or "").lower()
    if v.startswith("cisco_") or v == "arista_eos":
        return parse_ios(content)
    if v == "juniper_junos":
        return parse_junos(content)
    if v == "linux":
        return parse_linux(content)
    # Unknown vendor: try IOS-style as a best-effort fallback.
    return parse_ios(content)
