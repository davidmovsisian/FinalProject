import os
import base64
import requests
from io import BytesIO
from contextlib import asynccontextmanager
from typing import List, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from PIL import Image
from pydantic import BaseModel, HttpUrl
from fastapi import FastAPI, HTTPException
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms
from dotenv import load_dotenv

load_dotenv()

# =====================================================================
# 1. API Input/Output Schemas (Pydantic)
# =====================================================================
class UploadedImage(BaseModel):
    filename: str
    mime_type: str   # e.g. "image/jpeg", "image/png"
    data: str        # Raw base64-encoded image bytes (no data URI prefix)

class AnalysisRequest(BaseModel):
    # Expects a JSON list of URLs: ["http://...", "http://..."]
    image_urls: Optional[List[HttpUrl]] = []
    # Expects a JSON list of structured image objects:
    # [{"filename": "room.jpg", "mime_type": "image/jpeg", "data": "<base64>"}]
    uploaded_images: Optional[List[UploadedImage]] = []

class PredictionResult(BaseModel):
    room_type: str
    condition_score: float
    confidence: float


# =====================================================================
# 2. Encapsulated Multi-Task Neural Network Class
# =====================================================================
class MultiHeadResNet50(nn.Module):
    def __init__(self, num_classes: int, class_names: List[str] = None):
        super(MultiHeadResNet50, self).__init__()
        self.class_names = class_names or []
        
        # Build network architecture
        weights = models.ResNet50_Weights.DEFAULT
        self.backbone = models.resnet50(weights=weights)
        
        # Freeze convolutional backbone
        for param in self.backbone.parameters():
            param.requires_grad = False
            
        in_features = self.backbone.fc.in_features
        self.backbone.fc = nn.Identity()
        
        # Output classification & regression heads
        self.room_classifier = nn.Linear(in_features, num_classes)
        self.condition_regressor = nn.Linear(in_features, 1)

    def forward(self, x):
        features = self.backbone(x)
        room_out = self.room_classifier(features)
        condition_out = self.condition_regressor(features)
        return room_out, condition_out

    def train_model(self, train_loader: DataLoader, device: torch.device, epochs: int = 3):
        """Trains the classification and regression heads on a DataLoader."""
        self.train()
        class_criterion = nn.CrossEntropyLoss()
        reg_criterion = nn.MSELoss()
        
        trainable_params = [p for p in self.parameters() if p.requires_grad]
        optimizer = optim.Adam(trainable_params, lr=0.001)
        
        print("--> Starting training loop for the classifier and regression heads...")
        for epoch in range(epochs):
            running_loss = 0.0
            for images, room_labels, condition_scores in train_loader:
                images = images.to(device)
                room_labels = room_labels.to(device)
                condition_scores = condition_scores.to(device).unsqueeze(1)
                
                optimizer.zero_grad()
                room_preds, condition_preds = self(images)
                
                loss_class = class_criterion(room_preds, room_labels)
                loss_reg = reg_criterion(condition_preds, condition_scores)
                total_loss = loss_class + loss_reg
                
                total_loss.backward()
                optimizer.step()
                running_loss += total_loss.item() * images.size(0)
                
            print(f"    Epoch [{epoch+1}/{epochs}] completed. Avg Loss: {running_loss / len(train_loader.dataset):.4f}")

    def _run_inference(self, img: Image.Image, transform: transforms.Compose, device: torch.device) -> dict:
        """Shared inference logic: takes a PIL image, returns raw prediction values."""
        input_tensor = transform(img).unsqueeze(0).to(device)

        with torch.no_grad():
            room_logits, condition_out = self(input_tensor)

            # Extract probability and class index
            probabilities = F.softmax(room_logits, dim=1)
            conf_tensor, predicted_idx = torch.max(probabilities, 1)

            confidence = conf_tensor.item()
            pred_class = self.class_names[predicted_idx.item()]

            # Enforce reasonable continuous boundaries [1.0, 5.0]
            pred_condition = max(1.0, min(5.0, condition_out.item()))

        return {
            "room_type": pred_class,
            "condition_score": round(pred_condition, 2),
            "confidence": round(confidence, 2),
        }

    def predict_from_url(self, url: str, transform: transforms.Compose, device: torch.device) -> dict:
        """Downloads an image from a URL and returns prediction values."""
        self.eval()
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            img = Image.open(BytesIO(response.content)).convert('RGB')
        except Exception as e:
            raise ValueError(f"Failed to fetch or process image from URL {url}: {str(e)}")

        return self._run_inference(img, transform, device)

    def predict_from_uploaded(self, image: "UploadedImage", transform: transforms.Compose, device: torch.device) -> dict:
        """Decodes a structured UploadedImage (filename + mime_type + base64 data) and returns prediction values."""
        self.eval()
        try:
            image_bytes = base64.b64decode(image.data)
            img = Image.open(BytesIO(image_bytes)).convert('RGB')
        except Exception as e:
            raise ValueError(f"Failed to decode or process uploaded image '{image.filename}': {str(e)}")

        return self._run_inference(img, transform, device)


# =====================================================================
# 3. Custom Dataset Simulator (for fallback execution)
# =====================================================================
class HouseRoomsMultiTaskDataset(datasets.ImageFolder):
    """Extends ImageFolder to provide arbitrary mock condition scores during training."""
    def __getitem__(self, idx):
        image, room_label = super().__getitem__(idx)
        condition_score = torch.tensor(torch.randint(1, 6, (1,)).item(), dtype=torch.float32)
        return image, room_label, condition_score


# =====================================================================
# 4. Global State & FastAPI Lifetime Configuration
# =====================================================================
# Standard runtime configurations
APP_NAME = os.getenv("APP_NAME", "Multi-Task House Room Analyzer Engine")
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
WEIGHTS_PATH = os.getenv("WEIGHTS_PATH", "house_model_weights.pth")
DATASET_DIR = os.getenv("DATASET_DIR", "House_Room_Dataset")  

# Shared normalization transforms used universally
IMAGE_TRANSFORMS = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

# Global dictionary to safely expose the single loaded instance across tasks
app_state = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup orchestration: safely loading weights or spinning up training."""
    class_labels = ['Bathroom', 'Bedroom', 'Dinning', 'Kitchen', 'Livingroom']
    model = MultiHeadResNet50(num_classes=len(class_labels), class_names=class_labels)
    
    if os.path.exists(WEIGHTS_PATH):
        print(f"--> Found existing checkpoint '{WEIGHTS_PATH}'. Loading weights to {DEVICE}...")
        model.load_state_dict(torch.load(WEIGHTS_PATH, map_location=DEVICE))
    else:
        print(f"--> Checkpoint file '{WEIGHTS_PATH}' not found. Initializing training...")
        if not os.path.isdir(DATASET_DIR):
            raise RuntimeError(f"Cannot train! Data directory '{DATASET_DIR}' does not exist.")
            
        train_dataset = HouseRoomsMultiTaskDataset(root=DATASET_DIR, transform=IMAGE_TRANSFORMS)
        train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
        
        # Run training loop internally, then capture state to disk
        model.to(DEVICE)
        model.train_model(train_loader, DEVICE, epochs=3)
        torch.save(model.state_dict(), WEIGHTS_PATH)
        print(f"--> Training completed. Model parameters persisted to '{WEIGHTS_PATH}'.")

    model.to(DEVICE)
    model.eval()
    app_state["model"] = model  # Expose globally via dictionary reference
    yield
    # Cleanup actions if required can safely be placed here on shutdown
    # app_state.clear()


app = FastAPI(title="Multi-Task House Room Analyzer Engine", lifespan=lifespan)

@app.get("/health")
def health_check() -> dict:
    return {
        "status": "ok",
        "model_loaded": "model" in app_state,
        "device": str(DEVICE)
    }

# =====================================================================
# 5. REST Route Handlers
# =====================================================================
@app.post("/analyse", response_model=List[PredictionResult])
async def analyse_images(payload: AnalysisRequest):
    model: MultiHeadResNet50 = app_state.get("model")
    if not model:
        raise HTTPException(status_code=503, detail="Model architecture is currently uninitialized.")

    if not payload.image_urls and not payload.uploaded_images:
        raise HTTPException(
            status_code=422,
            detail="Request must include at least one entry in 'image_urls' or 'uploaded_images'."
        )

    results = []

    # --- Process URL-based images ---
    for url in payload.image_urls or []:
        try:
            prediction = model.predict_from_url(str(url), IMAGE_TRANSFORMS, DEVICE)
            results.append(prediction)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    # --- Process structured uploaded images ---
    for image in payload.uploaded_images or []:
        try:
            prediction = model.predict_from_uploaded(image, IMAGE_TRANSFORMS, DEVICE)
            results.append(prediction)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    return results