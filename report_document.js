const pages=document.getElementById('pages'),frame=document.getElementById('renderer'),progress=document.getElementById('progress'),printButton=document.getElementById('print');
const reportProgress=document.createElement('progress');reportProgress.max=report.jobs.length;reportProgress.value=0;progress.before(reportProgress);
const MM=96/25.4;
const downloadButton=document.createElement('button');downloadButton.textContent='Download HTML';downloadButton.disabled=true;downloadButton.id='download-html';printButton.before(downloadButton);
function downloadRenderedReport(){
  const copy=document.documentElement.cloneNode(true);
  for(const node of copy.querySelectorAll('script,iframe,progress,#download-html'))node.remove();
  const status=copy.querySelector('#progress');status.textContent=pages.children.length+' pages';
  copy.querySelector('#print').setAttribute('onclick','window.print()');
  const blob=new Blob(['<!doctype html>'+copy.outerHTML],{type:'text/html;charset=utf-8'}),url=URL.createObjectURL(blob),link=document.createElement('a');
  link.href=url;link.download=report.filename || 'profile-studio-report.html';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
downloadButton.addEventListener('click',downloadRenderedReport);
function dailyNotesText(events){
  const unique=new Map();for(const e of events || [])unique.set(e.date+'|'+e.minute+'|'+e.label,e);
  const labels=[...unique.values()].sort((a,b)=>a.minute-b.minute).map(e=>String(Math.floor(e.minute/60)).padStart(2,'0')+':'+String(Math.floor(e.minute%60)).padStart(2,'0')+' · '+e.label);
  return labels.length?'Notes: '+labels.join('; '):'';
}
function measureNote(body,text){
  if(!text)return 0;const note=textNote(text,'insight-note daily-notes');body.appendChild(note);const height=note.getBoundingClientRect().height+6;note.remove();return height;
}
function page(title){
  const section=document.createElement('section');section.className='page';section.dataset.title=title;
  const heading=document.createElement('h1');heading.textContent=title;section.appendChild(heading);
  const subtitle=document.createElement('div');subtitle.className='subtitle';subtitle.textContent=report.title+' · '+report.period;section.appendChild(subtitle);
  const body=document.createElement('div');body.className='body';section.appendChild(body);
  const footer=document.createElement('footer');for(const text of ['Profile Studio · '+report.generated,'Page '+(pages.children.length+1)]){const item=document.createElement('span');item.textContent=text;footer.appendChild(item);}section.appendChild(footer);pages.appendChild(section);
  const available=Math.floor(footer.getBoundingClientRect().top-body.getBoundingClientRect().top-8);
  if(available<80)throw new Error(title+': the title/header leaves no printable body space. Shorten the report title.');
  body.style.height=available+'px';return {section,body,available};
}
function textNote(text,cls='note'){const node=document.createElement('p');node.className=cls;node.textContent=text;return node;}
function contentHeight(p){return Math.max(0,...[...p.body.children].map(c=>c.getBoundingClientRect().bottom-p.body.getBoundingClientRect().top+(parseFloat(getComputedStyle(c).marginBottom)||0)));}
function fits(p){return p.body.scrollHeight<=p.available+1;}
function reportPageWeight(job,capacity){
  const nav=job.payload?.navigation,panels=nav?.saved_config?.panels;
  const compact=Array.isArray(panels)?panels.filter(p=>!p.deleted&&p.base==='compact:glucose').length:
    (job.payload?.specs || (job.figures || []).map(e=>e.figure) || []).filter(f=>f.layout?.meta?.kind==='compact').length;
  // Reserve the maximum possible Compact allocation for this configuration,
  // even on a day where an empty plot is omitted. Standard heights stay stable.
  return capacity+Math.min(capacity,compact);
}
function htmlPages(job){
  let p=page(job.title);p.body.innerHTML=job.html;if(fits(p))return;
  p.body.replaceChildren();const source=document.createElement('div');source.innerHTML=job.html;
  const nodes=[];function flatten(node){if(node.nodeType===1 && (node.classList.contains('overview-grid') || node.tagName==='DIV' && node.querySelector('table'))){for(const child of [...node.childNodes])flatten(child);}else nodes.push(node);}for(const node of [...source.childNodes])flatten(node);
  for(const node of nodes){
    if(node.nodeType===1 && node.tagName==='TABLE'){
      let table=node.cloneNode(false);if(node.tHead)table.appendChild(node.tHead.cloneNode(true));let tbody=document.createElement('tbody');table.appendChild(tbody);p.body.appendChild(table);
      for(const row of node.tBodies[0]?.rows || []){
        tbody.appendChild(row.cloneNode(true));if(fits(p))continue;
        const last=tbody.lastChild;last.remove();if(!tbody.children.length)table.remove();
        p=page(job.title);table=node.cloneNode(false);if(node.tHead)table.appendChild(node.tHead.cloneNode(true));tbody=document.createElement('tbody');table.appendChild(tbody);p.body.appendChild(table);tbody.appendChild(last);
        if(!fits(p))throw new Error(job.title+': one table row exceeds the printable height.');
      }
    }else{
      p.body.appendChild(node.cloneNode(true));if(fits(p))continue;
      const last=p.body.lastChild;last.remove();p=page(job.title);p.body.appendChild(last);
      if(!fits(p))throw new Error(job.title+': a text component exceeds the printable height.');
    }
  }
}
function render(payload){
  return new Promise((resolve,reject)=>{
    const id=payload.navigation.report_render.id;
    const timer=setTimeout(()=>finish(new Error('Chart rendering timed out for '+id+'.')),Math.max(120000,(payload.navigation.selected?.length || 1)*1000));
    function finish(error,figures){clearTimeout(timer);window.removeEventListener('message',receive);error?reject(error):resolve(figures);}
    function receive(event){if(event.source!==frame.contentWindow || event.data?.type!=='profile-studio:report-rendered' || event.data.id!==id)return;finish(event.data.error?new Error(event.data.error):null,event.data.figures);}
    window.addEventListener('message',receive);frame.srcdoc=report.template.replace('__REPORT_PAYLOAD__',()=>JSON.stringify(payload).replace(/</g,'\\u003c'));
  });
}
async function build(){
  try{
    if(document.fonts)await document.fonts.ready;
    // One measured slot budget per density/orientation; day-specific content cannot stretch it.
    const budgets=new Map(),weights=new Map();
    for(const job of report.jobs){
      if(job.html)continue;
      const capacity=job.graphs_per_page || report.graphs_per_page,p=page(job.title);
      weights.set(capacity,Math.max(weights.get(capacity) || capacity,reportPageWeight(job,capacity)));
      let notes=0;if(job.note){const note=textNote(job.note);p.body.appendChild(note);notes=note.getBoundingClientRect().height+8;}
      if(job.block==='daily'){
        const nav=job.payload?.navigation,range=nav?.report_render?.range || [0,1440];
        const ranges=[range],fit=(nav?.saved_config?.panels || []).some(p=>!p.deleted&&p.fitActivities);
        if(fit && nav.activity_bands?.length)ranges.push([Math.min(...nav.activity_bands.map(b=>b.x0)),Math.max(...nav.activity_bands.map(b=>b.x1))]);
        job.daily_note_reserve=measureNote(p.body,dailyNotesText((nav?.automation_notes || []).filter(e=>ranges.some(r=>e.minute>=r[0]&&e.minute<=r[1]))));
        notes+=job.daily_note_reserve;
      }
      const available=p.available-notes-2;
      budgets.set(capacity,Math.min(budgets.get(capacity) ?? Infinity,available));p.section.remove();
    }
    for(let i=0;i<report.jobs.length;i++){
      reportProgress.value=i;const job=report.jobs[i];progress.textContent='Preparing '+(i+1)+' / '+report.jobs.length+' · '+job.title;
      if(job.html){htmlPages(job);continue;}
      const capacity=job.graphs_per_page || report.graphs_per_page,probe=page(job.title);probe.body.classList.add('chart-stack');
      let notePixels=0;if(job.note){const note=textNote(job.note);probe.body.appendChild(note);notePixels=note.getBoundingClientRect().height+8;}
      notePixels+=job.daily_note_reserve || 0;
      const plotPixels=budgets.get(capacity),bodyWidth=probe.body.clientWidth,pageWeight=weights.get(capacity),slotMM=plotPixels/MM/pageWeight;
      probe.section.remove();
      const options={width:report.render_width,height:Math.floor(plotPixels/bodyWidth*report.render_width/pageWeight),compact:capacity>=3,capacity,note_width:bodyWidth,
        context_profiles:report.context_profiles || [],context_changes:report.context_changes || [],reserve_automation:report.reserve_automation,consolidate_automation:job.block==='daily'};
      let figures=[];
      if(job.payload){Object.assign(job.payload.navigation.report_render,options);figures=await render(job.payload);}
      else{
        const entries=job.figures || [{figure:job.figure,title:job.title}];
        const measured=entries.filter(e=>e.note).map(e=>{const note=textNote(e.note,'insight-note');note.style.cssText='width:'+bodyWidth+'px;font:8px/1.2 Arial,sans-serif;margin:0;padding:2px 0 0;';pages.appendChild(note);const pixels=note.getBoundingClientRect().height+2;note.remove();return pixels;});
        options.local_note_pixels=Math.max(0,...measured)*report.render_width/bodyWidth;
        for(let j=0;j<entries.length;j++){
          const entry=entries[j],figure=entry.figure;figure.layout.meta={...figure.layout.meta,non_time:true};
          const part=await render({specs:[figure],navigation:{report_render:{...options,id:'figure-'+i+'-'+j,range:[0,1440]},mode:'One day',days:[],selected:[],layers:[],unit:'',data_only:false,summaries:[]}});
          for(const f of part){f.note=entry.note||f.note;figures.push(f);}
        }
      }
      job.payload=null;job.figure=null;job.figures=null;
      const dailyNote=job.block==='daily'?dailyNotesText(figures.flatMap(f=>f.automation_notes || [])):'';
      let p=null,used=0,n=0;
      const finish=(last=false)=>{if(p&&job.note)p.body.appendChild(textNote(job.note));if(p&&last&&dailyNote)p.body.appendChild(textNote(dailyNote,'insight-note daily-notes'));p=null;used=0;n=0;};
      for(const f of figures){
        const slots=f.slots || 1;
        if(p&&n>=capacity)finish();
        if(!p){p=page(job.title);p.body.classList.add('chart-stack');}
        const row=document.createElement('div');row.className='report-chart';row.dataset.title=f.title;
        const image=document.createElement('img');image.src=f.url;image.alt=f.title||job.title;row.appendChild(image);p.body.appendChild(row);
        let localNote=0;if(f.note){const note=textNote(f.note,'insight-note');row.appendChild(note);localNote=note.getBoundingClientRect().height+2;}
        const total=slotMM*slots*MM;row.style.height=total+'px';image.style.height=Math.max(1,total-localNote)+'px';
        if(contentHeight(p)>p.available-notePixels+1){
          row.remove();if(n){finish();p=page(job.title);p.body.classList.add('chart-stack');p.body.appendChild(row);}else p.body.appendChild(row);
          if(contentHeight(p)>p.available-notePixels+1)throw new Error(job.title+' / '+f.title+': graph and notes exceed the printable body height.');
        }
        used+=slots;n++;
      }
      finish(true);
    }
    frame.srcdoc='';await Promise.all([...pages.querySelectorAll('img')].map(img=>img.decode()));
    for(const section of pages.children){const body=section.querySelector('.body');if(body.scrollHeight>body.clientHeight+2)throw new Error(section.dataset.title+': component exceeds its measured printable height.');}
    if(!pages.children.length)throw new Error('No data to print for the selected graphs and dates. Choose other dates or graphs and save the preset.');
    reportProgress.value=report.jobs.length;progress.textContent=pages.children.length+' pages ready';printButton.disabled=false;downloadButton.disabled=false;
  }catch(error){progress.textContent='Report failed: '+error.message;progress.className='error';}
}
printButton.addEventListener('click',()=>window.print());build();
