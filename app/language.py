"""Script/language hints and explicitly enabled local IndicTrans2 translation."""
from __future__ import annotations
import os, re, unicodedata

LANGS = {
 'English': {'script':'Latin','code':'eng_Latn'},
 'Hindi': {'script':'Devanagari','code':'hin_Deva'},
 'Kannada': {'script':'Kannada','code':'kan_Knda'},
}

def detect_language(text: str) -> dict:
    if re.search(r'[\u0c80-\u0cff]', text): return {'name':'Kannada','code':'kan_Knda','confidence':'high','method':'Unicode script detection'}
    if re.search(r'[\u0900-\u097f]', text): return {'name':'Hindi (Devanagari; other Devanagari languages may be confused)','code':'hin_Deva','confidence':'medium','method':'Unicode script detection'}
    if re.search(r'[\u0b80-\u0bff]', text): return {'name':'Tamil','code':None,'confidence':'high','method':'Unicode script detection'}
    if re.search(r'[\u0c00-\u0c7f]', text): return {'name':'Telugu','code':None,'confidence':'high','method':'Unicode script detection'}
    if any(
        ch.isalpha() and not unicodedata.name(ch, '').startswith('LATIN')
        for ch in text
    ):
        return {'name':'Unsupported script','code':None,'confidence':'high','method':'Unicode script detection; no translation route configured'}
    
    low=' '+re.sub(r'[^a-z ]',' ',text.lower())+' '
    kannada_hints={'enu','alla','hege','nanna','beku','yenu','aagide','thumba','mathu','roga','sari','thale','novu','nanage','nange','yake','illa','agutte','aaytu'}
    hindi_hints={'kya','hai','hain','mujhe','mera','meri','kaise','bukhar','dard','pet','chahiye','kyun'}
    words=set(low.split())
    if len(words & kannada_hints)>=2: return {'name':'Possible romanized Kannada / Kanglish','code':'kan_Latn','confidence':'low','method':'keyword heuristic; confirm language if needed'}
    if len(words & hindi_hints)>=2: return {'name':'Possible romanized Hindi / Hinglish','code':'hin_Latn','confidence':'low','method':'keyword heuristic; confirm language if needed'}
    return {'name':'English or romanized/code-mixed Latin input','code':'eng_Latn','confidence':'low','method':'Latin-script heuristic'}

class IndicTranslator:
    def __init__(self):
        self.enabled = False
        self.use_indic = os.environ.get('AYURMITRA_TRANSLATION','off').lower() in {'indictrans2','on','true','1'}
        self.enabled = self.use_indic
        self._models={}

    def _load(self, direction: str):
        if direction in self._models: return self._models[direction]
        try:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            from IndicTransToolkit import IndicProcessor
        except Exception as exc:
            raise RuntimeError('IndicTrans2 is not installed.') from exc
        model_name = ('ai4bharat/indictrans2-indic-en-1B' if direction=='to_en' else 'ai4bharat/indictrans2-en-indic-1B')
        tokenizer=AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        model=AutoModelForSeq2SeqLM.from_pretrained(model_name, trust_remote_code=True)
        model.eval(); processor=IndicProcessor(inference=True)
        self._models[direction]=(tokenizer,model,processor,torch)
        return self._models[direction]

    def translate(self, text: str, source_code: str, target_code: str) -> str:
        if source_code==target_code: return text
        
        # 1. Try IndicTrans2 if requested
        if self.use_indic:
            try:
                direction='to_en' if target_code=='eng_Latn' else 'from_en'
                tokenizer,model,processor,torch=self._load(direction)
                batch=processor.preprocess_batch([text], src_lang=source_code, tgt_lang=target_code)
                inputs=tokenizer(batch, truncation=True, padding='longest', return_tensors='pt')
                with torch.no_grad(): generated=model.generate(**inputs, max_length=256, num_beams=4, num_return_sequences=1)
                decoded=tokenizer.batch_decode(generated, skip_special_tokens=True)
                return processor.postprocess_batch(decoded, lang=target_code)[0]
            except Exception as exc:
                raise RuntimeError(f'IndicTrans2 translation failed: {exc}') from exc

        raise RuntimeError('Translation is disabled. Configure AYURMITRA_TRANSLATION=indictrans2 and install the optional model dependencies.')

translator=IndicTranslator()
