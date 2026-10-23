import sys, unittest
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.core import normalize, score_conditions, search_text_chunks, search_namaste_terms, find_imppat_use_tables, build_imppat_graph, _read_table

class CoreTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize("Heartburn,  NAUSEA!"),"heartburn nausea")

    def test_condition_association_ranking(self):
        df=pd.DataFrame([
            {"disease":"Condition A","symptom":"heartburn","disease_count_in_source":"20","disease_code":"A"},
            {"disease":"Condition A","symptom":"nausea","disease_count_in_source":"20","disease_code":"A"},
            {"disease":"Condition B","symptom":"cough","disease_count_in_source":"12","disease_code":"B"},
        ])
        result=score_conditions("heartburn and nausea",df)
        self.assertTrue(result)
        self.assertEqual(result[0]["condition"],"Condition A")
        self.assertEqual(len(result[0]["matched_symptoms"]),2)

    def test_who_text_retrieval(self):
        chunks=[{"text":"Ayurveda terminology includes digestive concepts","page":10},
                {"text":"Anatomical terminology and body structure","page":11}]
        hits=search_text_chunks("Ayurveda digestive concepts",chunks)
        self.assertTrue(hits)
        self.assertEqual(hits[0]["page"],10)

    def test_namaste_term_search_preserves_official_fields(self):
        df=pd.DataFrame([{"Code":"SAT-A-001","Word":"Agni","Short Definition":"digestive fire","source_sheet":"SAT-A"},
                         {"Code":"SAT-A-002","Word":"Vata","Short Definition":"dosha concept","source_sheet":"SAT-A"}])
        hits=search_namaste_terms("digestive fire",df)
        self.assertTrue(hits)
        self.assertEqual(hits[0]["Word"],"Agni")
        self.assertEqual(hits[0]["Code"],"SAT-A-001")
        self.assertIn("source_url",hits[0])

    def test_imppat_schema_adapter_and_graph(self):
        df=pd.DataFrame([{"Plant Name":"Ocimum tenuiflorum","Plant Part":"leaf","Therapeutic Use":"digestive discomfort"}])
        tables=[("fixture.csv",df)]
        rows=find_imppat_use_tables(tables)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["plant"],"Ocimum tenuiflorum")
        graph=build_imppat_graph(tables)
        self.assertEqual(graph.number_of_nodes(),2)
        self.assertEqual(graph.number_of_edges(),1)

    def test_imppat_official_export_column_names(self):
        df=pd.DataFrame([{"Indian medicinal plant":"Withania somnifera", "Plant part":"root", "Therapeutic use":"stress", "References":"ISBN:123"}])
        rows=find_imppat_use_tables([("imppat_plant_therapeutic_use.csv",df)])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["plant"],"Withania somnifera")
        self.assertEqual(rows[0]["therapeutic_use"],"stress")
        self.assertEqual(rows[0]["references"],"ISBN:123")


    def test_imppat_tab_delimited_csv_with_official_headers(self):
        import tempfile
        from app.core import search_imppat_uses
        with tempfile.TemporaryDirectory() as tmp:
            use_path=Path(tmp)/"imppat_plant_therapeutic_use.csv"
            info_path=Path(tmp)/"imppat_plant_info.csv"
            use_path.write_text("IMPPAT_Plant_identifier\tIndian_Medicinal_plant\tPlant_part\tIMPPAT_Therapeutic_use_identifier\tTherapeutic_use\nP001\tWithania somnifera\tRoot\tU001\tStress-related use\n", encoding="utf-8")
            info_path.write_text("Plant_identifier\tIndian_Medicinal_plant\tSynonymous names\tKingdom\tFamily\tGroup\tCommon_name\tIUCN_Red_List_Category\tSystem_of_Medicine\nP001\tWithania somnifera\tIndian ginseng\tPlantae\tSolanaceae\tHerb\tAshwagandha\tNA\tAyurveda\n", encoding="utf-8")
            uses=_read_table(use_path)
            info=_read_table(info_path)
            self.assertEqual(len(uses.columns),5)
            self.assertIn("Therapeutic_use", uses.columns)
            hits=search_imppat_uses("Main use of Ashwagandha", [(use_path.name, uses),(info_path.name, info)])
            self.assertTrue(hits)
            self.assertEqual(hits[0]["plant"], "Withania somnifera")

    def test_imppat_common_name_alias_search(self):
        from app.core import search_imppat_uses
        uses=pd.DataFrame([{"Indian medicinal plant":"Withania somnifera", "Plant part":"root", "Therapeutic use":"stress", "References":"ISBN:123"}])
        info=pd.DataFrame([{"Indian medicinal plant":"Withania somnifera", "Common name":"Ashwagandha", "Synonymous names":"Withania somnifera; Indian ginseng"}])
        hits=search_imppat_uses("Main use of Ashwagandha", [("imppat_plant_therapeutic_use.csv", uses), ("imppat_plant_info.csv", info)])
        self.assertTrue(hits)
        self.assertEqual(hits[0]["plant"], "Withania somnifera")

if __name__=="__main__": unittest.main()
