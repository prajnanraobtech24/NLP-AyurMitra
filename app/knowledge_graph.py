"""Provenance-preserving multi-source knowledge graph. Cross-source links are exact-label only."""
from __future__ import annotations
import re
import networkx as nx
from app.core import load_namaste_terms, load_columbia, load_imppat_tables, find_imppat_use_tables

def norm(value): return re.sub(r'[^a-z0-9]+',' ',str(value or '').lower()).strip()
def build_knowledge_graph():
    g=nx.MultiDiGraph()
    # NAMASTE term/code/definition nodes: preserve official row and sheet provenance.
    terms=load_namaste_terms()
    if not terms.empty:
        for idx,row in terms.iterrows():
            vals=row.to_dict(); label=next((str(v).strip() for k,v in vals.items() if any(x in str(k).lower() for x in ('word','term','name')) and str(v).strip()),'')
            if not label: continue
            code=next((str(v).strip() for k,v in vals.items() if 'code' in str(k).lower() and str(v).strip()),'')
            node='namaste::'+(code or f'{idx}:{norm(label)}')
            g.add_node(node,label=label,kind='ayurveda_term',source='NAMASTE',source_sheet=str(vals.get('source_sheet','')),code=code)
    # Columbia condition/symptom edges remain clearly identified as general clinical associations.
    df=load_columbia()
    if not df.empty and {'disease','symptom'}.issubset(df.columns):
        for idx,row in df.iterrows():
            disease=str(row.get('disease','')).strip(); symptom=str(row.get('symptom','')).strip()
            if not disease or not symptom: continue
            d='condition::'+norm(disease); s='symptom::'+norm(symptom)
            g.add_node(d,label=disease,kind='general_condition',source='Columbia Disease–Symptom Knowledge Database')
            g.add_node(s,label=symptom,kind='symptom',source='Columbia Disease–Symptom Knowledge Database')
            g.add_edge(s,d,relation='associated_with',source='Columbia Disease–Symptom Knowledge Database',source_row=int(idx))
    # IMPPAT plant/use associations.
    for row in find_imppat_use_tables(load_imppat_tables()):
        plant=str(row.get('plant','')).strip(); use=str(row.get('therapeutic_use','')).strip()
        if not plant or not use: continue
        p='plant::'+norm(plant); u='use::'+norm(use)
        g.add_node(p,label=plant,kind='medicinal_plant',source='IMPPAT 2.0')
        g.add_node(u,label=use,kind='source_listed_therapeutic_use',source='IMPPAT 2.0')
        g.add_edge(p,u,relation='source_lists_use',plant_part=str(row.get('plant_part','')),source='IMPPAT 2.0',source_file=str(row.get('source_file','')))
    # Cross-source links are made only for exact normalized labels; no inferred medical mapping.
    by_label={}
    for node,attrs in g.nodes(data=True):
        label=norm(attrs.get('label',''))
        if label: by_label.setdefault(label,[]).append(node)
    for label,nodes in by_label.items():
        if len(nodes)>1:
            for i,left in enumerate(nodes):
                for right in nodes[i+1:]:
                    if g.nodes[left].get('source') != g.nodes[right].get('source'):
                        g.add_edge(left,right,relation='exact_label_match_only',source='AyurMitra normalization layer')
    return g

def graph_summary():
    graph=build_knowledge_graph()
    kinds={}
    for _,data in graph.nodes(data=True): kinds[data.get('kind','unknown')]=kinds.get(data.get('kind','unknown'),0)+1
    relations={}
    for _,_,data in graph.edges(data=True): relations[data.get('relation','unknown')]=relations.get(data.get('relation','unknown'),0)+1
    return {'nodes':graph.number_of_nodes(),'edges':graph.number_of_edges(),'node_types':kinds,'relation_types':relations,
      'note':'Cross-source edges mean exact normalized label match only. Columbia associations are general clinical associations; IMPPAT use edges are source-listed associations, not personalized advice.'}
