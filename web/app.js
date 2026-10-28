const queryBox=document.getElementById('query'), searchButton=document.getElementById('search-button'), responsePanel=document.getElementById('response'), errorBox=document.getElementById('input-error'), languageHint=document.getElementById('language-hint');
const voiceButton=document.getElementById('voice-button'), speechLanguage=document.getElementById('speech-language'), voiceStatus=document.getElementById('voice-status');
let selectedCategory='general';
const categoryLabels={general:'GENERAL AYURVEDA',herbs:'AYURVEDIC HERBS',disease:'SYMPTOMS & CONDITIONS'};
const categoryPrompts={general:['Ask a general Ayurveda question','Try: What is Ayurveda? / What does Agni mean?'],herbs:['Search for an Ayurvedic herb or plant use','Try: Tulsi traditional uses / Withania somnifera'],disease:['Explore a symptom or condition in the sources','Try: stomach cramps / head pain / fever and cough']};

if (voiceButton) {
    const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        voiceButton.disabled=true;
        if(voiceStatus) voiceStatus.textContent='Voice input is not supported in this browser. Type or paste your question instead.';
    } else {
        let recognition=null;
        voiceButton.addEventListener('click',()=>{
            if(recognition){recognition.stop();return}
            recognition=new SpeechRecognition();
            recognition.lang=speechLanguage?.value||'en-IN';
            recognition.continuous=false;
            recognition.interimResults=false;
            recognition.maxAlternatives=1;
            recognition.onstart=()=>{voiceButton.textContent='Listening…';if(voiceStatus)voiceStatus.textContent='Speak your question. Your browser may ask for microphone access.'};
            recognition.onresult=event=>{
                const transcript=event.results?.[0]?.[0]?.transcript||'';
                if(transcript){queryBox.value=transcript;queryBox.dispatchEvent(new Event('input',{bubbles:true}));queryBox.focus()}
            };
            recognition.onerror=event=>{if(voiceStatus)voiceStatus.textContent=event.error==='not-allowed'?'Microphone access was blocked. You can type or paste your question.':'Voice recognition failed. Try again or type your question.'};
            recognition.onend=()=>{recognition=null;voiceButton.textContent='Speak question'};
            try{recognition.start()}catch(_){recognition=null;voiceButton.textContent='Speak question';if(voiceStatus)voiceStatus.textContent='Voice recognition could not start. Type or paste your question.'}
        });
    }
}

document.querySelectorAll('.topic-card').forEach(btn=>btn.addEventListener('click',()=>{
    selectedCategory=btn.dataset.category;
    document.querySelectorAll('.topic-card').forEach(b=>b.classList.toggle('active',b===btn));
    document.getElementById('query-label').textContent=categoryPrompts[selectedCategory][0];
    queryBox.placeholder=categoryPrompts[selectedCategory][1];
}));

function escapeHtml(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function detectScript(text){
    if(/[\u0C80-\u0CFF]/.test(text))return 'Kannada script detected; translation requires the optional IndicTrans2 model';
    if(/[\u0900-\u097F]/.test(text))return 'Devanagari detected; Hindi is inferred from script and may be ambiguous';
    if(/[\u0B80-\u0BFF]/.test(text))return 'Tamil script detected; translation is not configured';
    if(/[\u0C00-\u0C7F]/.test(text))return 'Telugu script detected; translation is not configured';
    const words=new Set(text.toLowerCase().replace(/[^a-z ]/g,' ').split(/\s+/));
    const kn=['enu','alla','hege','nanna','beku','yenu','aagide','thumba','thale','novu','nanage','nange'];
    const hi=['kya','hai','hain','mujhe','mera','meri','kaise','bukhar','dard','chahiye'];
    if(kn.filter(x=>words.has(x)).length>=2)return 'Possible romanized Kannada/Kanglish; language detection is uncertain';
    if(hi.filter(x=>words.has(x)).length>=2)return 'Possible romanized Hindi/Hinglish; language detection is uncertain';
    return 'English or romanized/code-mixed Latin input; romanized language detection is uncertain';
}

if (queryBox) {
    queryBox.addEventListener('input',()=>{if(languageHint) languageHint.textContent=detectScript(queryBox.value)});
    queryBox.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter')runSearch()});
}
if (searchButton) searchButton.addEventListener('click',runSearch);

function renderSources(sources){
    const holder=document.getElementById('sources');
    if(!holder) return;
    holder.innerHTML='';
    (sources||[]).forEach(src=>{
        const item=document.createElement('div');item.className='source-item';
        item.innerHTML=`<a href="${escapeHtml(src.url)}" target="_blank" rel="noopener">${escapeHtml(src.name)} ↗</a><p>${escapeHtml(src.detail||'')}</p>`;
        holder.appendChild(item);
    });
}

function renderResults(data){
  const holder=document.getElementById('results');
  if(!holder) return;
  holder.innerHTML='';
  
  if (data.xai_data && data.xai_data.length > 0) {
      const sectionEl = document.createElement('section');
      sectionEl.className = 'result-section';
      sectionEl.innerHTML = '<h3>Explainable Matches (Why these were chosen)</h3>';
      data.xai_data.forEach(item => {
          const card = document.createElement('div');
          card.className = 'xai-card';
          const symptomTags = item.matched_symptoms.map(s => `<span class="badge">${escapeHtml(s)}</span>`).join('');
          card.innerHTML = `
              <div class="xai-header">
                  <strong>${escapeHtml(item.condition)}</strong>
                  <span class="xai-score">Match Score: ${item.score} [${item.evidence_id}]</span>
              </div>
              <div class="xai-symptoms"><span>Matched Symptoms:</span> ${symptomTags}</div>
          `;
          sectionEl.appendChild(card);
      });
      holder.appendChild(sectionEl);
  }

  (data.sections||[]).forEach(section=>{
      const sectionEl=document.createElement('section');
      sectionEl.className='result-section';
      const heading=document.createElement('h3');
      heading.textContent=section.title;
      sectionEl.appendChild(heading);
      section.items.forEach(item=>{
          const card=document.createElement('details');
          card.className='result-card';
          const summary=document.createElement('summary');
          summary.textContent=item.title;
          card.appendChild(summary);
          const body=document.createElement('div');
          body.className='record-body';
          body.innerHTML=`<p>${escapeHtml(item.summary||'')}</p><p>${escapeHtml(item.detail||'')}</p><a class="record-source" href="${escapeHtml(item.source?.url||'#')}" target="_blank" rel="noopener">Source: ${escapeHtml(item.source?.name||'Reference')} ↗</a>`;
          card.appendChild(body);
          sectionEl.appendChild(card)
      });
      holder.appendChild(sectionEl)
  });
}

async function runSearch(){
    const query=queryBox.value.trim();
    const mode = document.getElementById('answer-mode') ? document.getElementById('answer-mode').value : 'ollama';
    const outputLanguage = document.getElementById('answer-language') ? document.getElementById('answer-language').value : 'auto';
    if(errorBox) errorBox.hidden=true;
    if(!query){if(errorBox){errorBox.textContent='Enter a question first.';errorBox.hidden=false;}return}
    
    searchButton.disabled=true;searchButton.querySelector('span').textContent='Searching…';
    try{
        const res=await fetch('/api/search',{
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({query, category:selectedCategory, answer_mode: mode, output_language: outputLanguage})
        });
        const data=await res.json();
        if(!res.ok)throw new Error(data.detail||'Search failed.');
        
        if(responsePanel) responsePanel.hidden=false;
        document.getElementById('summary').textContent=data.summary||'';
        document.getElementById('answer').textContent=data.answer||'No answer generated.';
        const languageBadge=document.getElementById('result-language');
        if(languageBadge) languageBadge.textContent='Input: '+(data.detected_language||'unknown')+' · Answer: '+(data.answer_language||'English');
        document.getElementById('answer-meta').textContent=`Mode: ${data.answer_mode||'retrieval'} · Lang: ${data.answer_language||'English'}`;
        
        const limits=document.getElementById('limitations');
        if(limits) limits.innerHTML=data.limitations?.length?`<ul>${data.limitations.map(x=>`<li>${escapeHtml(x)}</li>`).join('')}</ul>`:'';
        
        renderResults(data);
        renderSources(data.sources||[]);
        if(responsePanel) responsePanel.scrollIntoView({behavior:'smooth',block:'start'});
    }catch(err){
        if(errorBox){errorBox.textContent=err.message;errorBox.hidden=false}
    }finally{
        searchButton.disabled=false;
        searchButton.querySelector('span').textContent='Search sources';
    }
}
