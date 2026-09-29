# README 이미지 출처

## game-screen.jpg

현재 templates/index.html, static/style.css, static/script.js를 사용하는 로컬 UI 캡처. 카메라 영상 대신 검증 이미지, 인벤토리와 스캔 결과에는 예시 데이터를 사용했다. 실제 경기 기록이나 Gemini 호출 결과가 아니다.

## card-identification.jpg

- 입력 이미지: `AIBoardGame-4/valid/images/20251204_021050_jpg.rf.cef2fd1c653574c226fe036af600658b.jpg`
- 참조 이미지: `reference_imgs/l3_19.jpg`
- 실행 코드: `recognition.py`의 YOLO 모델 및 `BoardRecognizer._match`
- 식별 결과: `l3_19`, ratio test를 통과한 매칭 `48`개 (확률이 아님)
- 전처리: 너비 500px → 좌측 45%·하단 65% → 흑백 → CLAHE → AKAZE
- 단일 검증 이미지 사례이며 카드 ID 정확도 평가를 대체하지 않는다.
