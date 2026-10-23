"""Evaluate retrieval against a human-reviewed JSONL gold set; no fabricated labels/metrics."""
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from app.service import _flatten_evidence
from app.retrieval import hybrid_search

def main():
    gold=ROOT/'data/evaluation/gold_queries.jsonl'
    if not gold.exists(): print(f'Missing {gold.relative_to(ROOT)}. See data/evaluation/README.md; no metrics computed.'); return 2
    rows=[]
    for line in gold.read_text(encoding='utf-8').splitlines():
        if line.strip(): rows.append(json.loads(line))
    if not rows: print('Gold set is empty; no metrics computed.'); return 2
    records=_flatten_evidence(); recalls=[]; reciprocal=[]
    for row in rows:
        relevant=set(row.get('relevant_record_ids',[]))
        if not relevant: continue
        hits=hybrid_search(row['query'],records,top_k=5); ids=[str(x.get('id')) for x in hits]
        recalls.append(len(relevant & set(ids))/len(relevant))
        rank=next((i+1 for i,x in enumerate(ids) if x in relevant),None); reciprocal.append(1/rank if rank else 0)
    if not recalls: print('Gold set has no relevant_record_ids. No metrics computed.'); return 2
    report={'queries_evaluated':len(recalls),'recall_at_5':sum(recalls)/len(recalls),'mrr_at_5':sum(reciprocal)/len(reciprocal),'gold_set':'data/evaluation/gold_queries.jsonl','warning':'Metrics are meaningful only if labels are independently reviewed and queries are held out.'}
    out=ROOT/'data/processed/retrieval_evaluation.json'; out.write_text(json.dumps(report,indent=2),encoding='utf-8'); print(json.dumps(report,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
