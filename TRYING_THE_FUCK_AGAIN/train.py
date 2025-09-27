from ultralytics import YOLO

model = YOLO("yolov8n.pt")

model.train(
        data="Data/data.yaml",
        epochs=50,
        imgsz=416,
        batch=4,
        device='cpu',
        name="pest_Detect_small",
        project="models"
    )
