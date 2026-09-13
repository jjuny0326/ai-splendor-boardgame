from flask import Flask, jsonify, request, render_template
from game_logic import GameLogic
from llm_brain import LLMBrain
from recognition import BoardRecognizer
import time
import os
import random

app = Flask(__name__)

# [중요] 업로드 용량 제한 해제 (16MB까지 허용 -> 4K 사진 대응)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

# 임시 데이터 저장소
PENDING_DATA = {}

# 모듈 초기화
try:
    game_engine = GameLogic()
    ai_brain = LLMBrain()
    recognizer = BoardRecognizer()
    print("✅ 모든 모듈 로드 완료")
except Exception as e:
    print(f"❌ 초기화 오류: {e}")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/game_state', methods=['GET'])
def get_state():
    return jsonify(game_engine.get_state())

@app.route('/reset', methods=['POST'])
def reset_game():
    global PENDING_DATA
    PENDING_DATA = {}
    game_engine.reset_game()
    return jsonify({"status": "success", "current_state": game_engine.get_state()})

@app.route('/scan', methods=['POST'])
def scan_board():
    # 1. 이미지 받기
    if 'image' not in request.files: 
        return jsonify({"error": "이미지가 없습니다."}), 400
    
    file = request.files['image']
    file.save("temp.jpg")
    
    # 2. 인식 실행
    vision_data = recognizer.process_image("temp.jpg")
    
    # 안전장치 1: 아무것도 못 찾음
    total_gems = sum(vision_data['gems'].values())
    total_cards = sum(len(vision_data['cards_open'][lv]) for lv in ['level_1', 'level_2', 'level_3'])
    
    if total_cards == 0 and total_gems == 0:
        return jsonify({
            "status": "error",
            "message": "❌ 인식된 객체가 없습니다. 조명을 확인하거나 각도를 맞춰주세요."
        })

    # 3. 변화 추론
    changes = game_engine.infer_human_turn(vision_data)
    
    # 안전장치 2: 보석 급감 체크
    for gem, diff in changes['gem_diff'].items():
        if diff < -3:
            return jsonify({
                "status": "error",
                "message": f"⚠️ {gem} {abs(diff)}개 감소 감지. 인식 오류 같습니다."
            })

    # 4. 데이터 임시 저장
    global PENDING_DATA
    PENDING_DATA = {"changes": changes, "vision_data": vision_data}
    
    # recognition.py가 저장한 '진짜 파일명'을 가져옵니다.
    # (없을 경우를 대비해 기본값 설정)
    filename = vision_data.get('debug_file', 'debug_error.jpg')
    
    return jsonify({
        "status": "pending",
        "changes": changes,
        "vision_data": vision_data,
        "debug_img": f"/static/{filename}", # 정확한 파일명 연결!
        "message": "행동이 감지되었습니다."
    })

@app.route('/confirm_human', methods=['POST'])
def confirm_human():
    global PENDING_DATA
    if not PENDING_DATA: return jsonify({"error": "No data"}), 400
    
    game_engine.confirm_human_turn(PENDING_DATA['changes'], PENDING_DATA['vision_data'])
    PENDING_DATA = {}
    
    return jsonify({
        "status": "success", 
        "current_state": game_engine.get_state()
    })

@app.route('/ai_turn', methods=['POST'])
def ai_turn():
    current_state = game_engine.get_state()
    
    # AI 재시도 로직
    max_retries = 3
    feedback_msg = None
    
    for i in range(max_retries):
        print(f"🧠 AI 생각 중... (시도 {i+1}/{max_retries})")
        
        ai_action = ai_brain.get_ai_action(current_state, feedback=feedback_msg)
        success, msg = game_engine.apply_action('ai', ai_action)
        
        if success:
            return jsonify({
                "status": "success",
                "action": ai_action,
                "result": msg,
                "state": game_engine.get_state()
            })
        else:
            print(f"❌ AI 실수 ({msg}) -> 재교육 중...")
            feedback_msg = msg 
            
    return jsonify({
        "status": "fail",
        "action": ai_action,
        "result": "AI가 유효한 행동을 찾지 못했습니다. (규칙 위반 반복)",
        "state": game_engine.get_state()
    })

@app.route('/undo', methods=['POST'])
def undo_turn():
    success, msg = game_engine.undo_turn()
    
    if success:
        # 성공 시 이전 상태(점수 포함) 반환
        return jsonify({
            "status": "success", 
            "message": msg, 
            "current_state": game_engine.get_state()
        })
    else:
        return jsonify({"status": "fail", "message": msg})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '')
    current_state = game_engine.get_state()
    ai_response = ai_brain.get_chat_response(current_state, user_message)
    return jsonify({"response": ai_response})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)