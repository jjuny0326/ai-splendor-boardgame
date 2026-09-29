import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


class LLMBrainTests(unittest.TestCase):
    def test_retry_feedback_reaches_model(self):
        # 외부 SDK와 API 호출만 대체하고 실제 프롬프트 생성 코드를 실행한다.
        genai = types.ModuleType('google.generativeai')
        genai.configure = Mock()
        model = Mock()
        model.generate_content.return_value.text = '{"action": "resign"}'
        genai.GenerativeModel = Mock(return_value=model)
        google = types.ModuleType('google')
        google.generativeai = genai
        dotenv = types.ModuleType('dotenv')
        dotenv.load_dotenv = Mock()
        modules = {'google': google, 'google.generativeai': genai, 'dotenv': dotenv}
        source = Path(__file__).resolve().parents[1] / 'llm_brain.py'
        spec = importlib.util.spec_from_file_location('llm_brain_under_test', source)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules), patch.dict(os.environ, {'GEMINI_API_KEY': 'test-only'}):
            spec.loader.exec_module(module)
            brain = module.LLMBrain()
            result = brain.get_ai_action({}, feedback='ruby 재고 없음')
        self.assertEqual(result, {'action': 'resign'})
        self.assertIn('ruby 재고 없음', model.generate_content.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
