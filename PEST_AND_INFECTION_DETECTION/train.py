from ultralytics import YOLO

# Load pretrained YOLOv8 nano model
model = YOLO("yolov8n.pt")

# Train and save into a new model folder
model.train(
    data="TRAINING_MODEL/DATA/data.yaml",
    epochs=50,
    imgsz=416,
    batch=4,
    device="cpu",
    name="pest_Detect_small",
    project="models",  # save under a 'models' folder
)