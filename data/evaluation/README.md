# Retrieval evaluation set

Add human-reviewed test queries as JSON Lines in `gold_queries.jsonl`. Each line should contain:

```json
{"query":"English test query","relevant_record_ids":["WHO-P30-C55"],"language":"English","notes":"Why this record is relevant"}
```

Do not label records as relevant based only on the system's own ranking. Build a small reviewed gold set with the project supervisor/domain reviewer. Keep held-out evaluation queries separate from any tuning queries. The repository intentionally does not invent gold labels or report fabricated accuracy.
