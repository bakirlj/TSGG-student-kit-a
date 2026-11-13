#!/usr/bin/env python3
"""Starter: reads {"input": ..., "policy": ...} on stdin and writes one JSON answer on stdout.
Replace the body with your own program, in any language."""
import json
import sys

import cv2 


request = json.load(sys.stdin)
data, policy = request["input"], request["policy"]

img = cv2.imread(data["frame"])

assert img is not None, "Couldn't find any image, check the file name and folder"

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

code = "blurry" if sharpness < policy["blur_min_sharpness"] else None

# data["frame"] is a path such as "frames/blurry-1.png", relative to the root of your repo.
answer = {"code": code, "args": {"sharpness": round(sharpness,1)}}
json.dump(answer, sys.stdout)


