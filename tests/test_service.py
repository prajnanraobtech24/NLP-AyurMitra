import sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from app.service import search_project
from app.language import detect_language
from app.retrieval import bm25_scores, hybrid_search
from app.knowledge_graph import build_knowledge_graph
from app.rag import generate_grounded_answer
class ServiceTests(unittest.TestCase):
    def test_script_detection_kannada(self): self.assertEqual(detect_language('ತಲೆನೋವು')['name'],'Kannada')
    def test_script_detection_devanagari(self): self.assertIn('Hindi',detect_language('सिरदर्द')['name'])
    def test_romanized_detection_is_explicitly_uncertain(self): self.assertIn('Possible romanized',detect_language('mujhe bukhar hai')['name'])
    def test_non_english_query_not_silently_searched_when_translation_disabled(self):
        result=search_project('ತಲೆನೋವು'); self.assertFalse(result['translation_ready']); self.assertEqual(result['sections'],[]); self.assertEqual(result['answer_mode'],'translation unavailable')
    def test_empty_query_rejected(self):
        with self.assertRaises(ValueError): search_project('   ')
    def test_bm25_ranks_exactly_relevant_document(self):
        scores=bm25_scores('digestive fire',["Agni is associated with digestive fire",'plant taxonomy and leaves']); self.assertGreater(scores[0],scores[1])
    def test_hybrid_retrieval_returns_source_record(self):
        rows=[{'id':'a','text':'Agni is a digestive concept in Ayurveda'},{'id':'b','text':'leaf morphology and botany'}]
        hits=hybrid_search('Ayurveda digestive concept',rows); self.assertEqual(hits[0]['id'],'a')
    def test_knowledge_graph_is_provenance_safe(self):
        g=build_knowledge_graph(); self.assertIsNotNone(g); self.assertTrue(hasattr(g,'number_of_edges'))
    def test_rag_abstains_when_definition_is_not_supported(self):
        result=generate_grounded_answer('What is Agni?', [{'text':'A condition characterized by diminution of agni.','source_name':'WHO'}])
        self.assertEqual(result['answer_mode'],'grounded abstention')
    def test_rag_cites_supported_extractive_evidence(self):
        result=generate_grounded_answer('Agni', [{'text':'Agni is the digestive fire in this glossary entry.','source_name':'WHO'}])
        self.assertIn('[E1]',result['answer']); self.assertEqual(result['citations'],[1])
    def test_rag_does_not_turn_a_pdf_table_fragment_into_an_answer(self):
        result=generate_grounded_answer('Agni', [{'text':'capacity and weak person A condition characterized by diminution of agni.','source_name':'WHO'}])
        self.assertEqual(result['answer_mode'],'grounded abstention')
    def test_structured_plant_use_is_summarized_with_caveat(self):
        result=generate_grounded_answer('tulsi', [{'type':'plant_use','plant':'Ocimum tenuiflorum','therapeutic_use':'traditional respiratory use','plant_part':'leaf','text':'Plant: Ocimum tenuiflorum; therapeutic use: traditional respiratory use; plant part: leaf','source_name':'IMPPAT'}])
        self.assertIn('traditional respiratory use',result['answer'])
        self.assertIn('not proof',result['answer'])
    def test_invalid_category_rejected(self):
        with self.assertRaises(ValueError): search_project('Agni', 'invalid')
if __name__=='__main__': unittest.main()
