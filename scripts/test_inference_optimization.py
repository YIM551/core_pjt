import sys
from pathlib import Path
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from inference_optimization import ExactResultCache, is_simple_scene_question, bounded_setting, choose_vlm_side
from fastapi.testclient import TestClient
import main

class OptimizationTests(unittest.TestCase):
    def test_resolution_policy_preserves_uncertain_and_table_detail(self):
        self.assertEqual(choose_vlm_side([{'label':'Chair','confidence':.99}]),420)
        self.assertEqual(choose_vlm_side([{'label':'Sofa','confidence':.98}]),420)
        for objects in [[],[{'label':'Table','confidence':.99}],
                        [{'label':'Sofa','confidence':.67}],
                        [{'label':'Sofa','confidence':.98},{'label':'Table','confidence':.52}]]:
            self.assertEqual(choose_vlm_side(objects),448)

    def test_vlm_setting_validation(self):
        self.assertEqual(bounded_setting('392','side',112,1024),392)
        for value in ['bad','0','2048']:
            with self.assertRaises(ValueError):bounded_setting(value,'side',112,1024)

    def test_expiry_different_frame_and_capacity(self):
        now=[0]
        c=ExactResultCache(1,60,lambda:now[0])
        self.assertEqual(c.get_or_compute('a',lambda:'first'),('first',False))
        self.assertEqual(c.get_or_compute('a',lambda:'wrong'),('first',True))
        now[0]=61
        self.assertEqual(c.get_or_compute('a',lambda:'fresh'),('fresh',False))
        self.assertEqual(c.get_or_compute('b',lambda:'different'),('different',False))
        self.assertNotIn('a',c.entries)

    def test_single_flight(self):
        calls=[]
        c=ExactResultCache()
        def compute():
            calls.append(1)
            return 'result'
        with ThreadPoolExecutor(4) as pool:
            results=list(pool.map(lambda _:c.get_or_compute('same',compute),range(4)))
        self.assertEqual(len(calls),1)
        self.assertEqual(sum(not hit for _,hit in results),1)

    def test_errors_not_cached_and_disabled(self):
        c=ExactResultCache()
        with self.assertRaises(ValueError):
            c.get_or_compute('bad',lambda:(_ for _ in ()).throw(ValueError()))
        self.assertNotIn('bad',c.entries)
        disabled=ExactResultCache(0)
        self.assertFalse(disabled.get_or_compute('a',lambda:'x')[1])
        self.assertFalse(disabled.get_or_compute('a',lambda:'x')[1])

    def test_narrow_intent(self):
        self.assertTrue(is_simple_scene_question('어떤 가구가 보여?'))
        for prompt in ['위로 2칸 가','왼쪽','뭐가 보여? 그리고 오른쪽으로 가','의자는 무슨 색이야?','저쪽으로 가']:
            self.assertFalse(is_simple_scene_question(prompt))

    def test_fast_path_skips_llm_and_preserves_f206(self):
        client=TestClient(main.app)
        with patch.object(main,'SCENE_FAST_PATH',True),patch.object(main,'decide_tool',side_effect=AssertionError('Unnecessary LLM')):
            r=client.post('/api/llm-answer',json={'prompt':'어떤 가구가 보여?',
                'yolo_summary':'중복 후보: Sofa/Table (종류·개수 미확정)',
                'vlm_description':'테이블 위에 천이 있다, 장애물 없음.'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['inference_path'],'scene_evidence')
        self.assertTrue(r.json()['consistency']['has_conflict'])
        self.assertIn('미확정',r.json()['message'])
        self.assertIn('[VLM]',r.json()['message'])

    def test_movement_keeps_original_path(self):
        client=TestClient(main.app)
        result=({'tool':'move','args':{'direction':'up','steps':2},'message':'위로 2칸 이동합니다.'},'context')
        with patch.object(main,'decide_tool',return_value=result) as decide:
            r=client.post('/api/llm-answer',json={'prompt':'위로 2칸 가','yolo_summary':'Sofa 1개'})
        decide.assert_called_once()
        self.assertEqual(r.json()['inference_path'],'llm')
        self.assertEqual(r.json()['args'],{'direction':'up','steps':2})

if __name__=='__main__':unittest.main()
