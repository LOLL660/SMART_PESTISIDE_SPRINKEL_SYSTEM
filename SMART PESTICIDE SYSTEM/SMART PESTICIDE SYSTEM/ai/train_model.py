import os
import cv2
import numpy as np
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, Conv2D, MaxPooling2D, Flatten, Dense, concatenate
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import ModelCheckpoint

IMG_SIZE = 128  # smaller size to save memory

def load_images(rgb_dir, th_dir):
    X_rgb, X_th, Y = [], [], []
    for label, cls in enumerate(["healthy", "infested"]):
        rgb_path = os.path.join(rgb_dir, cls)
        th_path  = os.path.join(th_dir, cls)
        for f in os.listdir(rgb_path):
            rgb_file = os.path.join(rgb_path, f)
            th_file  = os.path.join(th_path, f)
            if os.path.exists(rgb_file) and os.path.exists(th_file):
                rgb = cv2.resize(cv2.imread(rgb_file), (IMG_SIZE, IMG_SIZE)) / 255.0
                th  = cv2.resize(cv2.imread(th_file, cv2.IMREAD_GRAYSCALE), (IMG_SIZE, IMG_SIZE)) / 255.0
                th  = th[..., None]
                X_rgb.append(rgb)
                X_th.append(th)
                Y.append(label)
    return np.array(X_rgb), np.array(X_th), np.array(Y)

# Load dataset
X_rgb, X_th, Y = load_images("dataset/train", "dataset/thermal")

# Build model
input_rgb = Input(shape=(IMG_SIZE, IMG_SIZE, 3))
x1 = Conv2D(16, 3, activation='relu')(input_rgb)
x1 = MaxPooling2D()(x1)
x1 = Flatten()(x1)

input_th = Input(shape=(IMG_SIZE, IMG_SIZE, 1))
x2 = Conv2D(16, 3, activation='relu')(input_th)
x2 = MaxPooling2D()(x2)
x2 = Flatten()(x2)

merged = concatenate([x1, x2])
output = Dense(1, activation='sigmoid')(merged)

model = Model([input_rgb, input_th], output)
model.compile(optimizer=Adam(0.001), loss='binary_crossentropy', metrics=['accuracy'])

# Save best model
checkpoint = ModelCheckpoint("armyworm_rgb_thermal.keras", monitor='accuracy', save_best_only=True)

# Train
model.fit([X_rgb, X_th], Y, epochs=10, batch_size=8, callbacks=[checkpoint])