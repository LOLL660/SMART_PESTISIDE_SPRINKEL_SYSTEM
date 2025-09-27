import os
from ultralytics import YOLO

# Load your trained model
model = YOLO('ai.pt')

# Input and output folders
input_folder = "test_images"
output_folder = "output"

# Create output folder if it doesn't exist
os.makedirs(output_folder, exist_ok=True)

# Loop through all files in input folder
for file_name in os.listdir(input_folder):
    file_path = os.path.join(input_folder, file_name)
    
    # Check if it's an image (you can add more extensions if needed)
    if file_name.lower().endswith(('.jpg', '.jpeg', '.png')):
        print(f"\nProcessing: {file_name}")
        
        # Run prediction
        results = model.predict(
            source=file_path,
            save=True,
            project=output_folder,   # output folder
            name="results",          # subfolder name inside output
            exist_ok=True            # don't overwrite, keep appending
        )

        # Process the results
        result = results[0]
        print(f"Total objects detected: {len(result.boxes)}")

        for box in result.boxes:
            coords = box.xyxy[0].tolist()
            confidence = round(box.conf.item(), 2)
            class_id = int(box.cls.item())
            class_name = model.names[class_id]

            print(f"  - Detected: {class_name} (ID: {class_id})")
            print(f"    Confidence: {confidence}")
            print(f"    Bounding Box: x_min={int(coords[0])}, y_min={int(coords[1])}, "
                  f"x_max={int(coords[2])}, y_max={int(coords[3])}")
