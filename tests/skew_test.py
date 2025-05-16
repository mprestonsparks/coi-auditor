import cv2
import numpy as np

# Load the image
img = cv2.imread("debug_page_image.png")

# Convert the image to grayscale
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# Threshold the image to create a binary image
thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

# Find contours in the binary image
contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

# Get the rotated rectangle that encloses the largest contour
rect = cv2.minAreaRect(max(contours, key=cv2.contourArea))

# Get the angle of rotation
angle = rect[-1]

# Correct the skew
if angle < -45:
    angle = -(90 + angle)
else:
    angle = -angle

(h, w) = img.shape[:2]
center = (w // 2, h // 2)
M = cv2.getRotationMatrix2D(center, angle, 1.0)
rotated = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

# Convert to grayscale
gray = cv2.cvtColor(rotated, cv2.COLOR_BGR2GRAY)

# Apply adaptive thresholding
thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

# Apply median blur for noise reduction
denoised = cv2.medianBlur(thresh, 3)

# Save the denoised image
cv2.imwrite("skew_corrected_binarized_denoised_image.png", denoised)