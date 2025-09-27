from ultralytics import YOLO


model = YOLO('yolov8n.pt')


results = model.predict(source='basic_test_image.png', conf=0.25, save=True)


result = results[0]

# Print a summary of the predictions
print(f"Total objects detected: {len(result.boxes)}")

# Iterate through the detected objects
for box in result.boxes:
    # Get the bounding box coordinates (normalized, then to pixels)
    # xyxy is format: [x_min, y_min, x_max, y_max]
    coords = box.xyxy[0].tolist() 
    
    # Get the confidence score (tensor -> float)
    confidence = round(box.conf.item(), 2) 
    
    # Get the class ID and name
    class_id = int(box.cls.item())
    class_name = model.names[class_id]
    
    # Print the details for each detection
    print(f"  - Detected: {class_name} (ID: {class_id})")
    print(f"    Confidence: {confidence}")
    print(f"    Bounding Box: x_min={int(coords[0])}, y_min={int(coords[1])}, x_max={int(coords[2])}, y_max={int(coords[3])}")