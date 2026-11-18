#!/usr/bin/env python3
"""Serve frozen V2 arithmetic for independent stock outline rasters."""
import json
import os
import sys

from v2_freetype_test import expected

for line in sys.stdin:
    value = json.loads(line)
    print(bytes(expected(value["raw"], value["high"], os.environ["FONTREAL_PROFILE"])).hex(), flush=True)
