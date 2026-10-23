from __future__ import annotations
import sys
from pathlib import Path
import streamlit as st
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.core import load_columbia, score_conditions, load_who_chunks, search_text_chunks, load_namaste_terms, search_namaste_terms, load_imppat_tables, search_imppat_uses, build_imppat_graph, dataset_status

st.set_page_config(page_title="AyurMitra Research Prototype",page_icon="🌿",layout="wide")
st.title("AyurMitra — symptom and Ayurveda knowledge explorer")
st.caption("Source-driven academic prototype • not a diagnostic or treatment tool")
st.warning("This app does not diagnose disease or prescribe herbs. General disease–symptom associations, WHO Ayurveda terminology, and IMPPAT plant-use associations are separate sources and must not be treated as a validated clinical chain.")

status=dataset_status()
imppat_tables=load_imppat_tables()
imppat_graph=build_imppat_graph(imppat_tables)
with st.expander("Dataset readiness",expanded=not all(status.values())):
    for name,ready in status.items(): st.write(("✅ " if ready else "❌ ")+name)
    if status.get("IMPPAT plant-use association table"):
        st.write(f"Local plant/use graph: {imppat_graph.number_of_nodes():,} nodes, {imppat_graph.number_of_edges():,} source-listed associations")
    if not all(status.values()):
        st.markdown("Run these commands in the project folder after installing requirements:")
        st.code("python scripts/download_datasets.py\npython scripts/prepare_datasets.py",language="powershell")
        st.caption("If IMPPAT auto-download fails, follow the manual fallback in docs/DATA_SOURCES.md.")

query=st.text_area("Describe symptoms or enter a term to search",placeholder="Example: heartburn and nausea",height=100)
if st.button("Search source data",type="primary"):
    if not query.strip(): st.info("Enter a symptom description or term first.")
    else:
        c1,c2=st.columns(2)
        with c1:
            st.subheader("1. General symptom–condition associations")
            df=load_columbia()
            matches=score_conditions(query,df)
            if matches:
                st.caption("Ranked by transparent text overlap against the source association table. Scores are not probabilities.")
                for m in matches:
                    with st.container(border=True):
                        st.markdown(f"**{m['condition']}**")
                        st.write("Matched source symptoms: "+", ".join(m["matched_symptoms"]))
                        st.caption(f"Overlap score: {m['score']} • Source disease count: {m['source_disease_count']} • {m['source_code']}")
            else: st.info("No matching source associations found in the prepared Columbia table for this query.")
        with c2:
            st.subheader("2. WHO Ayurveda terminology retrieval")
            hits=search_text_chunks(query,load_who_chunks())
            if hits:
                for hit in hits:
                    with st.container(border=True):
                        st.markdown(f"**WHO terminology document — page {hit.get('page','?')}**")
                        st.write(hit.get("text",""))
                        st.caption(f"Text similarity: {hit.get('similarity',0):.3f} • Source: {hit.get('source_url','')}")
            else: st.info("No WHO terminology text matched this query. Check Dataset readiness if you expected WHO data to be missing.")
        st.subheader("3. NAMASTE standardized Ayurveda terminology")
        namaste_df = load_namaste_terms()
        namaste_hits = search_namaste_terms(query, namaste_df)
        if namaste_hits:
            st.caption("Official terminology records. These standardize terms/codes; they do not independently validate a diagnosis.")
            for hit in namaste_hits:
                with st.container(border=True):
                    # Display the original source fields rather than inventing a common schema.
                    for key, value in hit.items():
                        if key in {"similarity", "source", "source_url"} or not str(value).strip(): continue
                        st.write(f"**{key}:** {value}")
                    st.caption(f"Text similarity: {hit.get('similarity', 0):.3f} • {hit.get('source_url', '')}")
        else:
            if namaste_df.empty:
                st.info("NAMASTE terminology data is not loaded. Run the dataset preparation script first.")
            else:
                st.info("No NAMASTE terminology record matched this query. This glossary standardizes Ayurveda terms; it is not a plant-use database, so an herb-name query may have no match.")
        st.subheader("4. IMPPAT plant–therapeutic-use associations")
        plant_hits=search_imppat_uses(query,imppat_tables)
        if plant_hits:
            for hit in plant_hits:
                with st.container(border=True):
                    st.markdown(f"**{hit['plant']}**")
                    st.write("Plant part: "+(hit.get("plant_part") or "not specified in the matched row"))
                    st.write("Source-listed therapeutic use: "+hit["therapeutic_use"])
                    st.caption(f"Text similarity: {hit['similarity']:.3f} • Source file: {hit['source_file']} • {hit['source_url']}")
                    if hit.get("references"):
                        st.write("Source references: " + hit["references"])
                    st.caption(hit["note"])
        else:
            from app.core import find_imppat_use_tables
            if not imppat_tables:
                st.info("No IMPPAT source tables are loaded. Check that the downloaded files are in data/raw/ and begin with imppat_.")
            elif not find_imppat_use_tables(imppat_tables):
                st.info("IMPPAT files were found, but the plant/use association columns were not recognized. Check the source column headers.")
            else:
                st.info("No IMPPAT plant/use row matched this query. Try a plant name or a source-listed therapeutic-use term.")

st.divider()
st.markdown("**Interpretation:** these are retrieval results from separate reference sources. They are not a diagnosis, personalised herb recommendation, or evidence that a plant treats the user's condition. Do not use them to select treatment or dosage.")
st.caption("Data provenance and licence notes: docs/DATA_SOURCES.md")
