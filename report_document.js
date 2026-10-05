const pages=document.getElementById('pages'),frame=document.getElementById('renderer'),progress=document.getElementById('progress'),printButton=document.getElementById('print');
const clock=()=>new Date().toLocaleTimeString();
function page(title,html,url,note){
  const section=document.createElement('section');section.className='page';
  const heading=document.createElement('h1');heading.textContent=title;section.appendChild(heading);
  const subtitle=document.createElement('div');subtitle.className='subtitle';subtitle.textContent=report.title+' · '+report.period;section.appendChild(subtitle);
  const body=document.createElement('div');body.className='body';
  if(html)body.innerHTML=html;
  if(url){const urls=Array.isArray(url)?url:[url];body.className+=' chart-stack';body.style.setProperty('--slot-height',report.chart_height_mm+'mm');for(const item of urls){const image=document.createElement('img');image.src=typeof item==='string'?item:item.url;if(item.slots)image.style.height=(report.chart_height_mm*item.slots)+'mm';image.alt=title;body.appendChild(image);}}
  if(note){const text=document.createElement('p');text.className='note';text.textContent=note;body.appendChild(text);}
  section.appendChild(body);const footer=document.createElement('footer');
  for(const text of ['Profile Studio · '+report.generated,'Page '+(pages.children.length+1)]){const item=document.createElement('span');item.textContent=text;footer.appendChild(item);}
  section.appendChild(footer);pages.appendChild(section);
}
function render(payload){
  return new Promise((resolve,reject)=>{
    const id=payload.navigation.report_render.id;
    const timer=setTimeout(()=>finish(new Error('Chart rendering timed out. Try fewer days or graphs.')),120000);
    function finish(error,figures){clearTimeout(timer);window.removeEventListener('message',receive);error?reject(error):resolve(figures);}
    function receive(event){
      if(event.source!==frame.contentWindow || event.data?.type!=='profile-studio:report-rendered' || event.data.id!==id)return;
      finish(event.data.error?new Error(event.data.error):null,event.data.figures);
    }
    window.addEventListener('message',receive);
    frame.srcdoc=report.template.replace('__REPORT_PAYLOAD__',()=>JSON.stringify(payload).replace(/</g,'\\u003c'));
  });
}
async function build(){
  try {
    for(let i=0;i<report.jobs.length;i++){
      const job=report.jobs[i];progress.textContent='Preparing '+(i+1)+' / '+report.jobs.length+' · '+job.title;
      if(job.html){page(job.title,job.html);continue;}
      let payload=job.payload;
      if(job.figure){
        const figure=job.figure;figure.layout.meta={...figure.layout.meta,non_time:true};
        payload={specs:[figure],navigation:{report_render:{id:'figure-'+i,range:[0,1440],width:report.render_width,height:report.render_height,compact:report.graphs_per_page>=3},mode:'One day',days:[],selected:[],layers:[],unit:'',data_only:false,summaries:[]}};
      }
      const figures=await render(payload);
      const mode=job.title.startsWith('Median')?'Median':job.title.startsWith('Daily')?'Daily':job.title.startsWith('All days')?'Overlay':null;
      const clean=t=>t.replace(/<[^>]*>/g,'').replace(/ · [0-9]{4}-[0-9]{2}-[0-9]{2}.*$/,'').replace(/^Median /,'');
      let group=[],used=0;
      const flush=()=>{if(!group.length)return;const labels=[...new Set(group.map(f=>clean(f.title)))];page(mode?mode+' — '+labels.join(', '):job.title,null,group,job.note);group=[];used=0;};
      for(const f of figures){const slots=f.slots || 1;if(used+slots>report.graphs_per_page)flush();group.push(f);used+=slots;}
      flush();
    }
    frame.srcdoc='';
    await Promise.all(Array.from(pages.querySelectorAll('img')).map(img=>img.decode()));
    // Do not silently print clipped tables; surface layout errors before export.
    for(const body of pages.querySelectorAll('.body'))if(body.scrollHeight>body.clientHeight+2)throw new Error('A report page exceeds its printable height. Reduce selected sleep overlays or split the report.');
    progress.textContent=pages.children.length+' pages ready';printButton.disabled=false;
  }catch(error){progress.textContent='Report failed: '+error.message;progress.className='error';}
}
printButton.addEventListener('click',()=>window.print());build();
