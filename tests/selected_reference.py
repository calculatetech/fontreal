#!/usr/bin/env python3
"""Serve the unchanged Python coverage reference to native raster probes."""
import json
import sys

from selected_profile_test import expected_mask


for line in sys.stdin:
    row = json.loads(line)
    mask = bytes.fromhex(row["mask"])
    width = row["width"]
    assert width >= 0 and (not mask or width > 0 and len(mask) % width == 0)
    output = expected_mask(mask, width) if mask else mask
    print(bytes(output).hex(), flush=True)
