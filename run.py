#!/usr/bin/env python3
"""Starter: reads {"input": ..., "policy": ...} on stdin and writes one JSON answer on stdout.
Replace the body with your own program, in any language."""
import json
import sys

import numpy as np
import cv2 

def check_blur(gray, policy):

    # Resize picture. Make new widt and height. 640 x 360
    h, w = gray.shape # Gives us the current height and width
    new_w = policy.get("blur_resize_width", 640) 
    new_h = round(h * new_w / w)
    small = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_AREA)
    # new w and h because resize takes width first, while shpae gives height first

    # Oval mask around the centre, where the bullseye is supposed to be
    mask = np.zeros((new_h, new_w), np.uint8) # makes all black picture same size as small
    center = (new_w // 2, new_h // 2) 
    axes = (int(new_w * policy.get("blur_roi_width", 0.7) / 2), 
            int(new_h * policy.get("blur_roi_height", 0.8) / 2))
    # drawing the mask
    cv2.ellipse(mask, center, axes, 0, 0, 360, 255, -1) 
    inside = mask > 0 #True inside oval, false otherwise

    # the brightness that 1% of the pixels are darker than, and
    # the brightness that 99% are darker than
    lo, hi = np.percentile(small[inside], [1, 99]) 
    stretched = (small.astype(np.float64) - lo) * (255.0 / max(hi - lo, 1))
    stretched = np.clip(stretched, 0, 255)

    lap = cv2.Laplacian(stretched, cv2.CV_64F)
    sharpness = float(lap[inside].var())

    # We compute the Laplacian on the whole picture then cut out the oval
    # Reason being if we cut and then measure, the cut would be super 
    # sharp between the edge and the cut. So it would give false information
    return {"sharpness": round(sharpness, 1)}

request = json.load(sys.stdin)
data, policy = request["input"], request["policy"]

img = cv2.imread(data["frame"]) 
assert img is not None, "Couldn't find any image, check the file name and folder"

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
blur = check_blur(gray, policy)

too_soft = blur["sharpness"] < policy.get("blur_min_sharpness", 200.0)
code = "blurry" if too_soft else None

answer = {"code": code, "args": blur}

json.dump(answer, sys.stdout)
