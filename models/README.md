# ShopGuard AI - Models Directory

This directory stores the object detection model weights used by ShopGuard AI.

## Default Model
The default model configured is **YOLO11n** (`yolo11n.pt`), a lightweight and fast model optimized for CPU inference on standard shop PCs.

## Automated Download
When ShopGuard AI is started for the first time, Ultralytics will automatically download the requested model weight file (`yolo11n.pt`) into this folder or the project root if internet access is present.

## Offline / Air-Gapped Setup
If the shop computer does not have persistent internet access:
1. Download `yolo11n.pt` (or `yolov8n.pt`) from the official Ultralytics releases:
   `https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt`
2. Place `yolo11n.pt` directly into this `models/` directory:
   `models/yolo11n.pt`
3. Verify the path in `config/config.yaml` points to `models/yolo11n.pt`.
