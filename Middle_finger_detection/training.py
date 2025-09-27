from ultralytics import YOLO

# Load pretrained YOLOv8 nano model
model = YOLO("yolov8n.pt")

# Train and save into a new model folder
model.train(
    data="data.yaml",
    epochs=50,
    imgsz=416,
    batch=4,
    device="cpu",
    name="middle_finger_model",
    project="models",  # save under a 'models' folder
)

