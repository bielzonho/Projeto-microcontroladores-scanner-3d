"""Numbers shared by the simulator and the detector.

With the real scanner these become CALIBRATION values that you measure
(see the guide). For now they describe an imaginary camera.
"""
import math

IMG_W, IMG_H = 640, 480   # camera image size, in pixels
PX_PER_MM = 6.0           # pixels that 1 mm of the object takes in the image
AXIS_COL = 320            # image column where the platform's rotation axis is
BASE_ROW = 440            # image row where the platform surface (z = 0) is
ALPHA_DEG = 45.0          # angle between the laser plane and the camera's view

SIN_ALPHA = math.sin(math.radians(ALPHA_DEG))
