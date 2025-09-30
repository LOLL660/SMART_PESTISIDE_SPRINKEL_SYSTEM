import cv2
import time
from ultralytics import YOLO
import sys

# --- Configuration ---
# 0 usually refers to the default camera (webcam or Pi Camera)
CAMERA_INDEX = 0 
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# CRITICAL: Replace this with the actual path to your trained YOLOv11 model file
MODEL_PATH = 'Pesticide-Detection-AI/FINAL_MODEL/ai.pt' 

# Confidence threshold to filter weak detections (adjust this value)
CONFIDENCE_THRESHOLD = 0.5

# --- Main Logic ---

def main():
    """Initializes YOLO model and runs the real-time camera detection loop."""
    
    # --- 1. Load YOLO Model ---
    try:
        # The YOLO class handles loading the model weights
        model = YOLO(MODEL_PATH)
        print(f"YOLOv11 Model loaded successfully from: {MODEL_PATH}")
    except Exception as e:
        print(f"FATAL ERROR: Could not load YOLO model at {MODEL_PATH}")
        print(f"Details: {e}")
        sys.exit(1)


    # --- 2. Initialize Camera ---
    cap = cv2.VideoCapture(CAMERA_INDEX)

    if not cap.isOpened():
        print("Error: Could not open camera. Check CAMERA_INDEX or permissions.")
        return

    # Set frame dimensions (important for stable performance)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    
    print(f"Camera feed started at {FRAME_WIDTH}x{FRAME_HEIGHT}. Press 'q' to exit.")
    
    frame_count = 0
    start_time = time.time()

    while True:
        # --- 3. Capture Frame ---
        ret, frame = cap.read()
        
        if not ret:
            print("Error: Could not read frame. Exiting.")
            break
            
        # Optional: Flip frame horizontally for easier webcam use
        frame = cv2.flip(frame, 1)

        # --- 4. Run YOLO Inference ---
        # The 'predict' method returns a list of Results objects
        results = model.predict(
            source=frame, 
            conf=CONFIDENCE_THRESHOLD,
            verbose=False # Keep terminal clean
        )

        # --- 5. Process and Display Results ---
        
        # 'results[0].plot()' uses the framework's built-in drawing function 
        # to draw the bounding boxes, labels, and confidence scores directly onto the frame.
        annotated_frame = results[0].plot()

        # --- 6. Display FPS (Optional but helpful) ---
        frame_count += 1
        elapsed_time = time.time() - start_time
        if elapsed_time > 1:
            fps = frame_count / elapsed_time
            cv2.putText(annotated_frame, f"FPS: {fps:.1f}", (FRAME_WIDTH - 100, 20), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            frame_count = 0
            start_time = time.time()


        # --- 7. Show Window and Handle Exit ---
        cv2.imshow('Real-Time Pest Detection (YOLOv11)', annotated_frame)

        # Exit loop if 'q' is pressed
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Cleanup
    cap.release()
    cv2.destroyAllWindows()
    print("\nYOLOv11 Detector terminated successfully.")

if __name__ == '__main__':
    main()