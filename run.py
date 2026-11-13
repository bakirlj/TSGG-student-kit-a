#!/usr/bin/env python3
"""Starter: reads {"input": ..., "policy": ...} on stdin and writes one JSON answer on stdout.
Replace the body with your own program, in any language."""
import json
import sys

request = json.load(sys.stdin)
data, policy = request["input"], request["policy"]

# data["frame"] is a path such as "frames/blurry-1.png", relative to the root of your repo.
answer = {"code": "not-checked", "args": {}}
json.dump(answer, sys.stdout)
