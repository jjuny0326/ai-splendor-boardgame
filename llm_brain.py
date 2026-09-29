# llm_brain.py
import json
import os
import re

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

class LLMBrain:
    def __init__(self):
        try: self.model = genai.GenerativeModel('models/gemini-2.5-flash')
        except: self.model = None

    def get_ai_action(self, game_state, feedback=None):
        state_str = json.dumps(game_state, indent=2, ensure_ascii=False)
        prompt = f"""
        당신은 스플렌더(Splendor) 2인 플레이 전문가 AI입니다.
        목표는 15점을 먼저 달성하여 승리하는 것입니다.

        [현재 2인 플레이 규칙 및 상황]
        1. **자원 희소성:** 보석이 색깔별로 단 4개뿐입니다. 보석이 마르면 게임이 정체됩니다.
        2. **보유 한도:** 보석은 최대 10개까지만 가질 수 있습니다. 10개가 넘지 않도록 주의하세요.
        3. **가져오기 규칙:** - 같은 색 보석 2개를 가져오려면, 보드판에 그 보석이 **4개 이상** 남아있어야 합니다.
        4. 보석도 없고, 살 수 있는 카드도 없는 '행동 불가' 상태라면 패배를 인정하세요.
        
        [현재 게임 상태]
        {state_str}

        [지시사항]
        위 상태를 분석하여 승률이 가장 높은 행동 하나를 선택하세요.
        구매 가능한 카드가 있다면 구매를 최우선으로 고려하세요.

        [응답 형식]
        반드시 아래 JSON 형식 중 하나로만 응답하세요. (설명 금지)
        
        - 카드 구매: {{"action": "buy_card", "card_id": "카드ID"}}
        - 보석 가져오기: {{"action": "take_gems", "gems": ["ruby", "sapphire", "onyx"]}}
        - 예약: {{"action": "reserve_card", "card_id": "..."}} 
           (※ 주의: 예약은 **바닥에 깔린 카드** 중에서만 선택하세요. 덱에서 뽑기는 불가능합니다.)
           (※ 전략: 상대방이 노리는 카드를 가로채거나, 조커(골드) 토큰이 급히 필요할 때 사용하세요.)
        - 항복: {{"action": "resign"}}
        """


        if feedback:
            prompt += f"\n[이전 행동 거절 사유]\n{feedback}\n이 사유를 해결하는 유효한 행동을 선택하세요.\n"

        try:
            res = self.model.generate_content(prompt)
            return json.loads(self._clean(res.text))
        except:
            return {"action": "take_gems", "gems": ["ruby", "sapphire", "emerald"]}

    def get_chat_response(self, game_state, user_msg):
        state_str = json.dumps(game_state, indent=2, ensure_ascii=False)
        prompt = f"""
        당신은 보드게임 '스플렌더'의 친절한 가이드이자 전략가입니다.
        사용자가 게임 중 궁금한 점을 물어보거나 조언을 구하고 있습니다.
        스플렌더 2인 게임을 기준으로 하고, 그 규칙은 다음과 같습니다.
        보석 토큰은 색깔별로 4개씩, gold 토큰만 5개 사용합니다.
        레벨1, 레벨2, 레벨3 카드는 전부 사용하고 그중 레벨별로 4장씩만 오픈, 귀족 타일은 3장만 사용합니다.
        스플렌더는 턴제로 진행이 되는 게임으로 자기 턴에 아래 중 하나의 동작을 할 수 있습니다.
        1) 각기 다른 색 보석 3개 가져오기
        2) 같은 색 보석 2개 가져오기 (단, 가져가려는 같은 색 보석이 4개 이상 테이블 위에 있을 때만 가능)
        3) 개발 카드 한 장 구매하기
        4) 바닥에 깔린 카드 예약하고 골드 토큰 1개 가져오기

        한 사람이 가지고 있을 수 있는 토큰의 수는 최대 10개입니다.


        [현재 게임 상태]
        {state_str}

        [사용자 질문]
        "{user_msg}"

        [답변 가이드라인]
        1. **현재 상황(보석 개수, 점수, 깔린 카드)을 근거로** 답변하세요. (상황 인지)
        2. 스플렌더 2인 플레이 기준으로 설명해주세요.
        2. 규칙 질문이면 명확하게 설명해주세요.
        3. 전략 질문이면 현재 자원을 분석해서 구체적인 행동(어떤 카드를 사라, 어떤 보석을 가져와라)을 추천해주세요.
        4. 한국어로 친절하고 간결하게(3문장 내외) 답변하세요.
        5. 규칙이나 전략을 묻지 않는다면 게임 관한 말은 하지 말고 그냥 질문에 대답해줘
        """
        try: return self.model.generate_content(prompt).text.strip()
        except: return "죄송합니다. 답변할 수 없습니다."

    def _clean(self, text):
        m = re.search(r'```json\n(.*?)\n```', text, re.DOTALL)
        if m: return m.group(1).strip()
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m: return m.group(0).strip()
        return text
