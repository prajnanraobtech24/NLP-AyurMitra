"""Provenance-preserving multi-source knowledge graph. Cross-source links are exact-label only."""
from __future__ import annotations
import re
from functools import lru_cache
import networkx as nx
from app.core import load_namaste_terms, load_columbia, load_imppat_tables, find_imppat_use_tables, load_who_chunks

SOURCE_URLS = {
    'NAMASTE': 'https://namaste.ayush.gov.in/sat_Ayurveda',
    'WHO': 'https://www.who.int/publications/i/item/9789240064935',
    'IMPPAT 3.0': 'https://cb.imsc.res.in/imppat/',
    'Columbia': 'https://impact.dbmi.columbia.edu/~friedma/Projects/DiseaseSymptomKB/index.html',
}

def norm(value): return re.sub(r'[^a-z0-9]+',' ',str(value or '').lower()).strip()
@lru_cache(maxsize=1)
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
            g.add_node(node,label=label,kind='ayurveda_term',source='NAMASTE',source_url=SOURCE_URLS['NAMASTE'],source_record=str(idx),source_sheet=str(vals.get('source_sheet','')),code=code,term_iast=str(vals.get('term_iast','')),term_devanagari=str(vals.get('term_devanagari','')),translation=str(vals.get('w_trans','')),definition=str(vals.get('w_def','')))
    # WHO passage nodes retain page/chunk provenance. Mention edges are textual
    # links only; they must not be read as treatment or causal relationships.
    for chunk in load_who_chunks():
        page=str(chunk.get('page','?')); chunk_id=str(chunk.get('chunk_id','?')); text=str(chunk.get('text',''))
        passage=f'who::page-{page}::chunk-{chunk_id}'
        g.add_node(passage,label=f'WHO Ayurveda terminology, page {page}, passage {chunk_id}',kind='reference_passage',source='WHO',source_url=SOURCE_URLS['WHO'],source_page=page,source_record=chunk_id,text=text[:1200])
        for topic in ('Ayurveda','Vata','Pitta','Kapha','Dosha','Agni','Prakriti','Vikriti','Charaka','Sushruta','Dhanvantari'):
            if re.search(rf'(?i)(?<![A-Za-z]){re.escape(topic)}(?![A-Za-z])',text):
                topic_node=f'who-topic::{norm(topic)}'
                g.add_node(topic_node,label=topic,kind='ayurveda_topic',source='WHO',source_url=SOURCE_URLS['WHO'])
                g.add_edge(passage,topic_node,key=f'mentions-{norm(topic)}',relation='passage_mentions_term',source='WHO',source_url=SOURCE_URLS['WHO'],source_page=page,source_record=chunk_id)
    # Columbia condition/symptom edges remain clearly identified as general clinical associations.
    df=load_columbia()
    if not df.empty and {'disease','symptom'}.issubset(df.columns):
        for idx,row in df.iterrows():
            disease=str(row.get('disease','')).strip(); symptom=str(row.get('symptom','')).strip()
            if not disease or not symptom: continue
            d='condition::'+norm(disease); s='symptom::'+norm(symptom)
            g.add_node(d,label=disease,kind='general_condition',source_url=SOURCE_URLS['Columbia'],source='Columbia Disease–Symptom Knowledge Database')
            g.add_node(s,label=symptom,kind='symptom',source_url=SOURCE_URLS['Columbia'],source='Columbia Disease–Symptom Knowledge Database')
            g.add_edge(s,d,relation='associated_with',source_url=SOURCE_URLS['Columbia'],source='Columbia Disease–Symptom Knowledge Database',source_row=int(idx))
    # IMPPAT plant/use associations.
    for row in find_imppat_use_tables(load_imppat_tables()):
        plant=str(row.get('plant','')).strip(); use=str(row.get('therapeutic_use','')).strip()
        if not plant or not use: continue
        p='plant::'+norm(plant); u='use::'+norm(use)
        g.add_node(p,label=plant,kind='medicinal_plant',source='IMPPAT 3.0',source_url=SOURCE_URLS['IMPPAT 3.0'])
        g.add_node(u,label=use,kind='source_listed_use',source='IMPPAT 3.0',source_url=SOURCE_URLS['IMPPAT 3.0'])
        g.add_edge(p,u,relation='source_lists_use',plant_part=str(row.get('plant_part','')),source='IMPPAT 3.0',source_url=SOURCE_URLS['IMPPAT 3.0'],source_file=str(row.get('source_file','')),references=str(row.get('references','')))
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

@lru_cache(maxsize=1)
def graph_summary():
    graph=build_knowledge_graph()
    kinds={}
    for _,data in graph.nodes(data=True): kinds[data.get('kind','unknown')]=kinds.get(data.get('kind','unknown'),0)+1
    relations={}
    for _,_,data in graph.edges(data=True): relations[data.get('relation','unknown')]=relations.get(data.get('relation','unknown'),0)+1
    sources={}
    for _,data in graph.nodes(data=True):
        source=data.get('source','unknown'); sources[source]=sources.get(source,0)+1
    return {'nodes':graph.number_of_nodes(),'edges':graph.number_of_edges(),'node_types':kinds,'relation_types':relations,'source_node_counts':sources,
      'note':'WHO edges record text mentions only. Columbia associations are general clinical associations; IMPPAT edges are source-listed use labels, not personalized advice. Exact-label cross-source edges do not imply medical equivalence.'}


def search_knowledge_graph(query: str, limit: int = 20) -> dict:
    """Search graph labels and return incident, provenance-bearing edges."""
    query_norm=norm(query); limit=max(1,min(int(limit),50))
    if not query_norm: return {'query':query,'nodes':[],'edges':[]}
    graph=build_knowledge_graph(); terms=set(query_norm.split()); ranked=[]
    for node,data in graph.nodes(data=True):
        label=norm(data.get('label','')); overlap=len(terms & set(label.split()))
        if query_norm in label or overlap:
            score=3 if label==query_norm else 2 if query_norm in label else overlap
            ranked.append((score,node,data))
    ranked.sort(key=lambda row:(-row[0],str(row[2].get('label','')).lower(),row[1]))
    selected=ranked[:limit]; selected_ids={node for _,node,_ in selected}; edges=[]
    # Include a small neighborhood so a matching WHO topic exposes the source
    # passage that mentions it, even when the passage title itself has no topic.
    frontier=set(selected_ids)
    for _ in range(2):
        related_ids=set()
        for source,target,_,_ in graph.edges(keys=True,data=True):
            if source in frontier: related_ids.add(target)
            if target in frontier: related_ids.add(source)
        frontier=set()
        for node in sorted(related_ids, key=lambda item: str(graph.nodes[item].get('label','')).lower()):
            if node not in selected_ids and len(selected_ids) < limit * 3:
                selected_ids.add(node)
                selected.append((0,node,graph.nodes[node]))
                frontier.add(node)
    edges=[]
    for source,target,key,data in graph.edges(keys=True,data=True):
        if source in selected_ids or target in selected_ids:
            edges.append({'source':source,'target':target,'key':key,**data})
            if len(edges)>=limit*4: break
    return {'query':query,'nodes':[{'id':node,**data} for _,node,data in selected],'edges':edges}
