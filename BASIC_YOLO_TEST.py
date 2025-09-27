from ultralytics import YOLO

# Load the pretrained YOLOv8-nano model
model = YOLO("yolov8n.pt")  # pretrained on COCO

# Run detection on an image
results = model("basic_test_image.jpg")

# Show results
results.show()  # Opens image with bounding boxes
