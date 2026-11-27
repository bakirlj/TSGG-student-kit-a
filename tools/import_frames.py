"""Convert camera pictures (BMP, or anything OpenCV reads) to PNG with a lowercase label-N name.

Usage: python tools/import_frames.py SRC NEW_NAME [SRC NEW_NAME ...]
Example: python tools/import_frames.py frames/Blurry-1.bmp ok-1
PNG is lossless, so the pixels stay identical; only the file gets smaller.
"""
import os
import sys

import cv2
import numpy as np


def main(args):
    if not args or len(args) % 2:
        sys.exit(__doc__)
    for src, name in zip(args[::2], args[1::2]):
        img = cv2.imread(src, cv2.IMREAD_COLOR)
        if img is None:
            sys.exit(f"cannot read {src}")
        dst = os.path.join(os.path.dirname(src), name.lower() + ".png")
        cv2.imwrite(dst, img, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        assert np.array_equal(cv2.imread(dst), img), f"{dst} differs from {src}"
        print(f"{src} -> {dst} ({os.path.getsize(src) >> 20} MB -> {os.path.getsize(dst) >> 20} MB)")


if __name__ == "__main__":
    main(sys.argv[1:])
