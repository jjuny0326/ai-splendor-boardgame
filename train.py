# train.py
import os

from dotenv import load_dotenv
from roboflow import Roboflow
from ultralytics import YOLO

load_dotenv()

# 1. Roboflow에서 데이터셋 내려받기
rf = Roboflow(api_key=os.environ["ROBOFLOW_API_KEY"])
project = rf.workspace("aiboardgame").project("aiboardgame-nko9n")
version = project.version(4)

# 2. 데이터셋 다운로드
# 프로젝트가 Object Detection 타입이므로 "yolov8" 포맷을 사용합니다.
print("데이터셋 다운로드 중...")
dataset = version.download("yolov8")

# 3. 모델 학습
print(f"🚀 학습 시작! 데이터 경로: {dataset.location}")
model = YOLO("yolov8n.pt")  # detection 전용 사전학습 모델

results = model.train(
    data=f"{dataset.location}/data.yaml",
    epochs=50,
    imgsz=640,
    plots=True,
)
