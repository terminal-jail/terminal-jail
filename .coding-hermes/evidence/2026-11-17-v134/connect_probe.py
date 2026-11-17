#!/usr/bin/env python3
"""Dogfood 2026-11-17: kernel-egress-tier probe. Prints errno per TCP connect attempt."""

import socket
import sys

TARGETS = [
    (("1.1.1.1", 4444), "port-4444 (NOT allowlisted)"),
    (("example.com", 443), "443 (allowlisted default)"),
]

for (host, port), label in TARGETS:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(6)
    try:
        s.connect((host, port))
        print(f"{label}: CONNECTED")
    except socket.timeout:
        print(f"{label}: TIMEOUT")
    except OSError as e:
        print(f"{label}: errno={e.errno} {e.strerror}")
    finally:
        s.close()
sys.stdout.flush()
