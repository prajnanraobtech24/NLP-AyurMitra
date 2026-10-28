import io, json, os, sys, unittest
import pandas as pd
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from app.service import search_project
from app.core import canonical_symptom_terms
from app.language import detect_language
from app.retrieval import bm25_scores, correct_query_spelling, hybrid_search
from app.knowledge_graph import build_knowledge_graph, search_knowledge_graph
from app.rag import generate_grounded_answer, _directly_supporting_evidence, _ollama_answer
class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.no_model = patch.dict(os.environ, {'AYURMITRA_OLLAMA_MODEL':''})
        self.no_model.start()
        self.addCleanup(self.no_model.stop)
    def test_script_detection_kannada(self): self.assertEqual(detect_language('ತಲೆನೋವು')['name'],'Kannada')
    def test_script_detection_devanagari(self): self.assertIn('Hindi',detect_language('सिरदर्द')['name'])
    def test_romanized_detection_is_explicitly_uncertain(self): self.assertIn('Possible romanized',detect_language('mujhe bukhar hai')['name'])
    def test_non_english_query_not_silently_searched_when_translation_disabled(self):
        result=search_project('ತಲೆನೋವು'); self.assertFalse(result['translation_ready']); self.assertEqual(result['sections'],[]); self.assertIn('grounded abstention',result['answer_mode'].lower())
    def test_scripts_without_a_translation_route_do_not_search_english(self):
        for query in ('\u0985\u09ae\u09bf', '\u0ba4\u0bae\u0bbf\u0bb4\u0bcd', '\u0c05'):
            with self.subTest(query=query):
                result=search_project(query)
                self.assertEqual(result['sections'],[])
                self.assertIn('grounded abstention',result['answer_mode'].lower())
    def test_unsupported_script_uses_labeled_ollama_answer_without_local_evidence(self):
        payload=json.dumps({'response':'आयुर्वेद भारत की एक पारंपरिक ज्ञान प्रणाली है।'}).encode()
        with patch.dict(os.environ, {'AYURMITRA_OLLAMA_MODEL':'test-model'}), \
             patch('app.rag.urllib.request.urlopen', return_value=io.BytesIO(payload)):
            result=search_project('आयुर्वेद क्या है?')
        self.assertEqual(result['sections'],[])
        self.assertIn('not based on local records',result['answer_mode'])
        self.assertIn('[AI-generated; not based on local records]',result['answer'])
        self.assertIn('आयुर्वेद',result['answer'])
    def test_empty_query_rejected(self):
        with self.assertRaises(ValueError): search_project('   ')
    def test_bm25_ranks_exactly_relevant_document(self):
        scores=bm25_scores('digestive fire',["Agni is associated with digestive fire",'plant taxonomy and leaves']); self.assertGreater(scores[0],scores[1])
    def test_hybrid_retrieval_returns_source_record(self):
        rows=[{'id':'a','text':'Agni is a digestive concept in Ayurveda'},{'id':'b','text':'leaf morphology and botany'}]
        hits=hybrid_search('Ayurveda digestive concept',rows); self.assertEqual(hits[0]['id'],'a')
    def test_knowledge_graph_is_provenance_safe(self):
        g=build_knowledge_graph(); self.assertIsNotNone(g); self.assertTrue(hasattr(g,'number_of_edges'))

    def test_knowledge_graph_search_keeps_source_provenance_and_relationship_types(self):
        build_knowledge_graph.cache_clear()
        terms=pd.DataFrame([{'term_iast':'pitta','term_devanagari':'पित्त','w_trans':'pitta','w_def':'traditional concept','source_sheet':'SAT'}])
        columbia=pd.DataFrame([{'disease':'Example condition','symptom':'headache'}])
        plant=[{'plant':'Withania somnifera','therapeutic_use':'stress','plant_part':'root','source_file':'use.csv','references':'ref'}]
        with patch('app.knowledge_graph.load_namaste_terms',return_value=terms), \
             patch('app.knowledge_graph.load_who_chunks',return_value=[{'page':52,'chunk_id':9,'text':'Pitta regulates body temperature.'}]), \
             patch('app.knowledge_graph.load_columbia',return_value=columbia), \
             patch('app.knowledge_graph.load_imppat_tables',return_value=[]), \
             patch('app.knowledge_graph.find_imppat_use_tables',return_value=plant):
            graph=build_knowledge_graph()
            result=search_knowledge_graph('pitta',5)
        self.assertTrue(any(row['kind']=='reference_passage' for row in result['nodes']))
        self.assertTrue(any(row['relation']=='passage_mentions_term' and row['source_page']=='52' for row in result['edges']))
        edge=next(data for _,_,data in graph.edges(data=True) if data.get('relation')=='source_lists_use')
        self.assertEqual(edge['source'],'IMPPAT 3.0')
        self.assertEqual(edge['plant_part'],'root')
        self.assertFalse(any(data.get('relation') in {'treats','recommends'} for _,_,data in graph.edges(data=True)))
        build_knowledge_graph.cache_clear()
    def test_rag_abstains_when_definition_is_not_supported(self):
        result=generate_grounded_answer('What is Agni?', [{'text':'A condition characterized by diminution of agni.','source_name':'WHO'}])
        self.assertEqual(result['answer_mode'],'grounded abstention')
    def test_rag_cites_supported_extractive_evidence(self):
        result=generate_grounded_answer('Agni', [{'text':'Agni is the digestive fire in this glossary entry.','source_name':'WHO'}])
        self.assertIn('[E1]',result['answer']); self.assertEqual(result['citations'],[1])
    def test_rag_does_not_turn_a_pdf_table_fragment_into_an_answer(self):
        result=generate_grounded_answer('Agni', [{'text':'capacity and weak person A condition characterized by diminution of agni.','source_name':'WHO'}])
        self.assertEqual(result['answer_mode'],'grounded abstention')
    def test_rag_ignores_unrelated_namaste_definitions(self):
        result=generate_grounded_answer('Agni', [
            {'type':'terminology','text':'term_iast: pradhāna-karma; w_def: main procedures'},
            {'type':'terminology','text':'term_iast: agni-utkleśaḥ; w_def: diminution of agni'},
            {'type':'terminology','text':'term_iast: agni; w_def: digestive fire'},
        ])
        self.assertIn('agni refers to digestive fire',result['answer'].lower())
        self.assertNotIn('pradhāna-karma',result['answer'])
        self.assertNotIn('agni-utkleśaḥ',result['answer'])
        self.assertEqual(result['citations'],[3])
    def test_rag_does_not_answer_generic_query_with_random_namaste_terms(self):
        result=generate_grounded_answer('Tell me about Ayurveda', [
            {'type':'terminology','text':'term_iast: pradhāna-karma; w_def: main procedures'},
        ])
        self.assertEqual(result['answer_mode'],'grounded abstention')
        self.assertNotIn('pradhāna-karma',result['answer'])
    def test_ollama_answers_without_local_evidence_and_labels_it(self):
        payload=json.dumps({'response':'Ayurveda is a traditional health knowledge system.'}).encode()
        with patch.dict(os.environ, {'AYURMITRA_OLLAMA_MODEL':'test-model'}), \
             patch('app.rag.urllib.request.urlopen', return_value=io.BytesIO(payload)):
            result=generate_grounded_answer('What is Ayurveda?', [], answer_mode_setting='ollama')
        self.assertIn('Ayurveda is a traditional',result['answer'])
        self.assertIn('not based on local records',result['answer_mode'])
        self.assertEqual(result['citations'],[])
    def test_extractive_mode_uses_labeled_general_fallback_if_needed(self):
        payload=json.dumps({'response':'Ayurveda includes several classical knowledge traditions.'}).encode()
        with patch.dict(os.environ, {'AYURMITRA_OLLAMA_MODEL':'test-model'}), \
             patch('app.rag.urllib.request.urlopen', return_value=io.BytesIO(payload)):
            result=generate_grounded_answer('Tell me about Ayurveda', [], answer_mode_setting='extractive')
        self.assertIn('Ayurveda includes',result['answer'])
        self.assertIn('not based on local records',result['answer_mode'])
        self.assertEqual(result['citations'],[])
    def test_structured_plant_use_is_summarized_with_caveat(self):
        result=generate_grounded_answer('tulsi', [{'type':'plant_use','plant':'Ocimum tenuiflorum','therapeutic_use':'traditional respiratory use','plant_part':'leaf','text':'Plant: Ocimum tenuiflorum; therapeutic use: traditional respiratory use; plant part: leaf','source_name':'IMPPAT'}])
        self.assertIn('traditional respiratory use',result['answer'])
        self.assertIn('not proof',result['answer'])

    def test_plain_symptom_response_hides_noisy_condition_list(self):
        result=search_project('stomach cramps','disease')
        self.assertIn('stomach pain or cramps',result['answer'])
        self.assertIn('pain abdominal',result['answer'])
        self.assertIn('not a diagnosis',result['answer'])
        self.assertNotIn('adenocarcinoma',result['answer'].lower())
        self.assertEqual(len(result['sections']),1)

    def test_ollama_evidence_requires_citation(self):
        evidence=[{'type':'symptom_association','text':'Matching source symptom labels: pain abdominal','matched_symptoms':['pain abdominal'],'source_name':'Columbia'}]
        with patch('app.rag.urllib.request.urlopen',return_value=io.BytesIO(json.dumps({'response':'The source mentions abdominal pain.'}).encode())):
            self.assertIsNone(_ollama_answer('stomach cramps',evidence,'English','test-model'))

    def test_plain_ayurveda_query_matches_visarga_term(self):
        result=search_project('ayurveda','general')
        self.assertTrue(any(section['title']=='NAMASTE Standardized Ayurveda Terminologies' for section in result['sections']))
        self.assertIn('science of life',result['answer'].lower())

    def test_everyday_ayurveda_meaning_question_uses_local_term_record(self):
        result=search_project('What does Ayurveda mean?','general')
        self.assertEqual(result['answer_mode'],'Extractive answer')
        self.assertIn('science of life',result['answer'].lower())
        self.assertTrue(any(section['title']=='NAMASTE Standardized Ayurveda Terminologies' for section in result['sections']))

    def test_father_of_ayurveda_question_uses_nuanced_official_source_answer(self):
        result=search_project('Who is the father of Ayurveda?','general')
        self.assertIn('does not assign one person',result['answer'].lower())
        self.assertIn('Charaka',result['answer'])
        self.assertIn('Dhanvantari',result['answer'])
        self.assertEqual(result['answer_citations'],[1])
        self.assertIn('Ministry of AYUSH',result['sections'][0]['title'])

    def test_everyday_pitta_question_uses_who_definition(self):
        result=search_project('What does Pitta mean in everyday terms?','general')
        self.assertIn('body temperature and metabolic activities',result['answer'])
        self.assertIn('[E',result['answer'])

    def test_dosha_comparison_defines_all_three_from_who(self):
        result=search_project('How do Vata, Pitta and Kapha differ?','general')
        self.assertIn('Vata is described',result['answer'])
        self.assertIn('Pitta is described',result['answer'])
        self.assertIn('Kapha is described',result['answer'])

    def test_numeric_three_doshas_question_gets_who_definitions(self):
        result=search_project('what are the 3 doshas and how does ayurveda describe them?','general')
        self.assertIn('Vata is described',result['answer'])
        self.assertIn('Kapha is described',result['answer'])

    def test_typos_map_to_the_intended_topic(self):
        result=search_project('Ayurvedaa meaning','general')
        self.assertIn('science of life',result['answer'].lower())
        self.assertIn('Likely spelling correction',result['limitations'][-1])

    def test_spelling_variants_for_headache_map_to_headache(self):
        self.assertEqual(canonical_symptom_terms('headachee and dizziness'),['headache'])
        self.assertEqual(canonical_symptom_terms('I have head achee'),['headache'])

    def test_plant_question_does_not_substitute_unrelated_plant(self):
        result=search_project('Which tulsi uses are listed in the dataset?','herbs')
        self.assertIn('Ocimum tenuiflorum',result['answer'])
        self.assertNotIn('Gymnema',result['answer'])

    def test_fuzzy_spelling_correction_matches_corpus_terms(self):
        records=[{'text':'Withania somnifera Ashwagandha medicinal plant'}]
        self.assertIn('ashwagandha',correct_query_spelling('ashwaganda',records).lower())

    def test_unrelated_general_records_cannot_trigger_unsupported_ai_claims(self):
        result=generate_grounded_answer('Who is the father of Ayurveda?',[
            {'type':'terminology','text':'term_iast: pitta-kopanam; w_def: substances that vitiate pitta doṣa'}
        ],answer_mode_setting='ollama')
        self.assertEqual(result['answer_mode'],'grounded abstention')
        self.assertNotIn('Charaka',result['answer'])

    def test_pitta_definition_does_not_support_unsourced_remedy_advice(self):
        evidence=[{'type':'terminology','text':'term_iast: pitta; w_trans: pitta; w_def: a traditional concept'}]
        self.assertEqual(_directly_supporting_evidence('How can I reduce pitta safely?',evidence),[])

    def test_unsupported_pitta_action_skips_slow_ollama_call(self):
        evidence=[{'type':'terminology','text':'Term ID English term Description Sanskrit term ITA-2.1.2.1 Pitta, dosha regulating body temperature and metabolic activities Pitta is'}]
        with patch('app.rag._ollama_answer') as model:
            result=generate_grounded_answer('How can I reduce pitta safely?',evidence,'English','ollama')
        model.assert_not_called()
        self.assertIn('grounded abstention',result['answer_mode'].lower())

    def test_explicit_answer_language_translates_grounded_answer(self):
        with patch('app.service.translate_answer_with_ollama',return_value='Ayurveda ka arth jeevan ka vigyan hai [E1]'):
            result=search_project('ayurveda','general','extractive','hindi')
        self.assertEqual(result['answer_language'],'Hindi')
        self.assertIn('[E1]',result['answer'])

    def test_english_preference_is_respected_for_hindi_input(self):
        result=search_project('\u092e\u0941\u091d\u0947 \u092c\u0941\u0916\u093e\u0930 \u0939\u0948','general','extractive','english')
        self.assertEqual(result['answer_language'],'English')
        self.assertFalse(result['translation_ready'])

    def test_auto_language_reports_english_fallback_when_translation_unavailable(self):
        result=search_project('\u092e\u0941\u091d\u0947 \u092c\u0941\u0916\u093e\u0930 \u0939\u0948','general','extractive','auto')
        self.assertEqual(result['answer_language'],'English (Hindi response unavailable)')

    def test_invalid_output_language_rejected(self):
        with self.assertRaises(ValueError): search_project('hello','general','extractive','french')
    def test_invalid_category_rejected(self):
        with self.assertRaises(ValueError): search_project('Agni', 'invalid')
if __name__=='__main__': unittest.main()
