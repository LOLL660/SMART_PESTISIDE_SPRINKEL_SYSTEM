import cv2
import numpy as np
from tensorflow.keras.models import load_model

IMG_SIZE = 128

# Load trained model
model = load_model("armyworm_rgb_thermal.keras")

# Function to preprocess webcam frame
def preprocess_frame(frame):
    rgb = cv2.resize(frame, (IMG_SIZE, IMG_SIZE))
    th  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    th  = cv2.resize(th, (IMG_SIZE, IMG_SIZE))
    th  = th[..., None]  # add channel dimension

    rgb = rgb / 255.0
    th  = th / 255.0

    rgb = np.expand_dims(rgb, axis=0)
    th  = np.expand_dims(th, axis=0)

    return rgb, th

# Real-time webcam prediction
cap = cv2.VideoCapture(0)
print("Press 'q' to quit")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    rgb, th = preprocess_frame(frame)
    pred = model.predict([rgb, th])[0][0]
    label = "Infested" if pred > 0.5 else "Healthy"

    # Display prediction on webcam
    cv2.putText(frame, f"Prediction: {label}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)
    cv2.imshow("AI Detection", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):  # press 'q' to quit
        break

cap.release()
cv2.destroyAllWindows()

import datetime

def log_detection(pest_coordinates, battery_level):
    with open("detections.log", "a") as f:
        f.write(f"{datetime.datetime.now()}, Pests: {pest_coordinates}, Battery: {battery_level}\n")