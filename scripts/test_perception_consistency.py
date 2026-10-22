"""F206 regressions: ambiguity, explicit counts, missing information, source enforcement."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from perception_consistency import analyze_detections, reconcile, grounded_description

class EvidenceTests(unittest.TestCase):
    def test_table_conflict_does_not_select_higher_confidence_sofa(self):
        objects=[{'label':'Sofa','confidence':.676,'box':[1.7,316.5,1175.3,1034.2]},
                 {'label':'Table','confidence':.526,'box':[.4,306.9,1180.1,1069]}]
        r=analyze_detections(objects)
        self.assertEqual(r['certain_counts'], {})
        self.assertEqual(r['ambiguous_indices'], [0,1])
        self.assertGreater(r['cross_class_overlaps'][0]['iou'], .8)
        self.assertEqual(objects[0]['confidence'], .676)
        evidence=reconcile(r['summary'],'테이블 위에 체크무늬 천이 깔려 있다, 장애물 없음.')
        self.assertTrue(evidence['has_conflict'])
        self.assertIn('미확정',grounded_description(r['summary'],'테이블 위에 천이 있다.',evidence))

    def test_separate_objects_not_flagged(self):
        r=analyze_detections([{'label':'Sofa','box':[0,0,10,10]}, {'label':'Table','box':[20,20,30,30]}])
        self.assertEqual(r['certain_counts'], {'Sofa':1,'Table':1})
        self.assertFalse(r['cross_class_overlaps'])

    def test_explicit_count_conflict(self):
        r=reconcile('Chair 2개','의자 하나가 놓여 있다, 장애물 있음.')
        self.assertEqual(r['issues'][0]['type'],'count_mismatch')
        self.assertEqual(r['vlm_explicit_counts'],{'Chair':1})

    def test_unspecified_or_missing_not_zero(self):
        for text in ['방에 의자가 있다.', '거실이다.', '소파가 한쪽에 있다.']:
            self.assertFalse(reconcile('Chair 2개, Sofa 1개',text)['has_conflict'])

    def test_matching_count_and_citations(self):
        r=reconcile('Sofa 1개','소파 하나가 있다.')
        self.assertFalse(r['has_conflict'])
        message=grounded_description('Sofa 1개','소파 하나가 있다.',r)
        self.assertIn('[YOLO]',message)
        self.assertIn('[VLM]',message)

if __name__=='__main__':
    unittest.main()
