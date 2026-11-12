const $ = s => document.querySelector(s);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const date = value => new Date(value).toLocaleString('pt-BR', {dateStyle:'short',timeStyle:'short'});
const badge = value => `<span class="badge ${esc(value)}">${esc(value)}</span>`;
let tickets = [], view = 'tickets', currentId, docCategory = '';
const categories=['Geral','Acesso','Rede','Hardware','Software','Processos'];
let documentCache=[];
let currentUser=null,csrfToken='',ticketRequest=0;
const isStaff=()=>currentUser&&currentUser.role!=='requester';
async function api(path, method='GET', body) {
  const sessionToken=csrfToken;
  const response = await fetch('/api'+path,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':csrfToken},body:body ? JSON.stringify(body):undefined});
  const data = await response.json();
  if(!path.startsWith('/auth/')&&sessionToken!==csrfToken)throw new Error('A sessão foi alterada. Atualize a página.');
  if(response.status===401&&path!=='/auth/login'){showLogin('Sua sessão terminou. Entre novamente.');}
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Confira os campos e tente novamente.');
  return data;
}
function error(e) { $('#notice').textContent=e.message; $('#notice').hidden=false; if($('#modal').open){let alert=$('#modal-error');if(!alert){alert=document.createElement('p');alert.id='modal-error';alert.setAttribute('role','alert');alert.style.cssText='padding:14px;background:#fff0e9;color:#9b4934;border-radius:7px';$('#modal-content').prepend(alert);}alert.textContent=e.message;alert.scrollIntoView({block:'nearest'});} }
function modal(title, html) { $('#modal-title').textContent=title; $('#modal-content').innerHTML=html; if(!$('#modal').open) $('#modal').showModal(); }
$('#close').onclick=()=>{ticketRequest++;$('#modal').close();};
$('#modal').addEventListener('cancel',()=>ticketRequest++);
function slaBadge(t) {
  const labels={on_track:'Dentro do prazo',warning:'Prazo próximo',overdue:'Atrasado',met:'Resolvido no prazo',breached:'Resolvido fora do prazo'};
  return `<span class="sla-badge ${t.sla.state}">${labels[t.sla.state]}</span><small class="sla-date">${date(t.sla.due_at)}</small>`;
}
function renderTickets() {
  const selectedOwner=$('#owner-filter').value;
  const owners=[...new Set(tickets.map(t=>t.assignee).filter(Boolean))].sort();
  $('#owner-filter').innerHTML='<option value="">Todos os responsáveis</option><option value="unassigned">Não atribuídos</option>'+owners.map(o=>`<option value="person:${esc(o)}">${esc(o)}</option>`).join('');
  $('#owner-filter').value=[...$('#owner-filter').options].some(o=>o.value===selectedOwner)?selectedOwner:'';
  const overdue=tickets.filter(t=>t.sla.state==='overdue').length, warning=tickets.filter(t=>t.sla.state==='warning').length;
  $('#sla-alert').hidden=!overdue&&!warning;
  $('#sla-alert').textContent=`Atenção aos prazos: ${overdue} chamado(s) atrasado(s) e ${warning} próximo(s) do vencimento.`;
  const stats=[['Total de chamados',tickets.length,'▤'],['Em aberto',tickets.filter(t=>t.status==='Aberto').length,'◷'],['Em andamento',tickets.filter(t=>['Em análise','Aguardando usuário'].includes(t.status)).length,'↗'],['Resolvidos',tickets.filter(t=>t.status==='Resolvido').length,'✓']];
  $('#stats').innerHTML=stats.map(([label,n,icon])=>`<div class="stat"><p>${label}<small>${icon}</small></p><strong>${n.toString().padStart(2,'0')}</strong></div>`).join('');
  const query=$('#search').value.toLowerCase(), status=$('#filter').value;
  const owner=$('#owner-filter').value, slaState=$('#sla-filter').value;
  const filtered=tickets.filter(t=>(!status||t.status===status)&&(!owner||(owner==='unassigned'?!t.assignee:'person:'+t.assignee===owner))&&(!slaState||t.sla.state===slaState)&&`${t.title} ${t.requester} ${t.assignee} ${t.id}`.toLowerCase().includes(query));
  const order=$('#sort').value;
  const rank={'Crítica':0,'Alta':1,'Média':2,'Baixa':3};
  if(order==='deadline')filtered.sort((a,b)=>(a.status==='Resolvido')-(b.status==='Resolvido')||new Date(a.sla.due_at)-new Date(b.sla.due_at));
  if(order==='priority')filtered.sort((a,b)=>rank[a.priority]-rank[b.priority]);
  $('#count').textContent=filtered.length;
  $('#rows').innerHTML=filtered.map(t=>`<tr><td><a href="#chamado-${t.id}" data-ticket="${t.id}">${esc(t.title)}</a><small>#${String(t.id).padStart(4,'0')} · ${esc(t.category)}</small></td><td>${esc(t.requester)}</td><td>${badge(t.priority)}</td><td>${badge(t.status)}</td><td>${esc(t.assignee||"Não atribuído")}</td><td>${slaBadge(t)}</td><td>${date(t.created_at)}</td></tr>`).join('');
  $('#empty').hidden=filtered.length>0;
  if(tickets.length && !filtered.length) {$('#rows').innerHTML='<tr><td colspan="7">Nenhum chamado corresponde aos filtros.</td></tr>';$('#empty').hidden=true;}
  document.querySelectorAll('[data-ticket]').forEach(el=>el.onclick=e=>{e.preventDefault();openTicket(Number(el.dataset.ticket)).catch(error);});
}
async function refresh(){tickets=await api('/tickets');renderTickets();}
$('#search').oninput=renderTickets;$('#filter').onchange=renderTickets;$('#owner-filter').onchange=renderTickets;$('#sla-filter').onchange=renderTickets;
function newTicket(){
  modal('Novo chamado',`<form id="ticket-form"><label for="title">O que aconteceu?</label><input id="title" name="title" required minlength="3" maxlength="180" placeholder="Ex.: Não consigo acessar o sistema"><label for="requester">Solicitante</label><input id="requester" name="requester" required minlength="2" maxlength="180" placeholder="Nome ou e-mail"><label for="description">Descrição do problema</label><textarea id="description" name="description" required minlength="10" maxlength="15000" placeholder="Informe o erro, quando começou, quantas pessoas foram afetadas e o que já tentou."></textarea><div class="actions"><button class="primary">Criar chamado</button></div><p class="muted">Não inclua senhas ou dados sensíveis.</p></form>`);
  if(currentUser?.role==='requester'){$('#requester').value=currentUser.name;$('#requester').readOnly=true;}
  $('#ticket-form').onsubmit=async e=>{e.preventDefault();const button=e.submitter;button.disabled=true;try{const t=await api('/tickets','POST',Object.fromEntries(new FormData(e.target)));await refresh();await openTicket(t.id);}catch(err){error(err);}finally{button.disabled=false;}};
}
$('#first-ticket').onclick=newTicket;
async function openTicket(id,fromId=null){
 const request=++ticketRequest,userId=currentUser?.id;
 currentId=id; const t=await api('/tickets/'+id), a=t.analysis;
 if(request!==ticketRequest||currentUser?.id!==userId)return;
 modal(`#${String(id).padStart(4,'0')} · ${t.title}`,`${fromId?`<button id="related-back" class="subtle">← Voltar ao chamado #${fromId}</button>`:''}<div class="detail-meta">${badge(t.priority)} ${badge(t.category)}<span class="muted">${esc(t.requester)} · ${date(t.created_at)}</span></div><p class="detail-description">${esc(t.description)}</p><section class="similar-panel"><div class="similar-heading"><h3>Chamados semelhantes</h3><label class="check-label"><input id="similar-resolved" type="checkbox"> Somente resolvidos</label></div><p class="muted">Sugestões por termos em comum. Casos parecidos podem ter causas diferentes.</p><div id="similar-results" aria-live="polite">Buscando casos anteriores…</div></section>${attachmentPanel(t)}<section class="sla-detail"><h3>Prazo de resolução</h3>${slaBadge(t)}<p class="muted">${t.sla.hours} horas corridas desde a abertura. O status Aguardando usuário não pausa o prazo.</p></section><form id="assignment-form" class="assignment-form"><div><label for="assignee">Responsável pelo atendimento</label><input id="assignee" maxlength="180" value="${esc(t.assignee)}" placeholder="Nome do atendente"><datalist id="assignees">${[...new Set(tickets.map(item=>item.assignee).filter(Boolean))].map(name=>`<option value="${esc(name)}">`).join('')}</datalist></div><div><label for="ticket-priority">Prioridade confirmada</label><select id="ticket-priority">${['Baixa','Média','Alta','Crítica'].map(p=>`<option ${p===t.priority?'selected':''}>${p}</option>`).join('')}</select></div><button type="submit">Salvar atendimento</button></form><p class="muted">Alterar a prioridade recalcula o SLA desde a abertura, sem reiniciar a contagem.</p><label for="status">Status do chamado</label><select id="status">${['Aberto','Em análise','Aguardando usuário','Resolvido'].map(s=>`<option ${s===t.status?'selected':''}>${s}</option>`).join('')}</select><div class="actions"><button class="primary" id="analyze">✧ ${a?'Gerar nova análise':'Analisar com IA local'}</button></div><p class="muted">A classificação só é aplicada após sua aprovação. A análise pode levar até três minutos.</p>${a?`<div class="analysis"><h3>✧ Sugestão da IA · ${esc(a.model)}</h3><p>${esc(a.reason)}</p><div class="detail-meta"><div><label for="category">Categoria</label><select id="category">${['Acesso','Rede','Software','Hardware','Outros'].map(s=>`<option ${s===a.category?'selected':''}>${s}</option>`).join('')}</select></div><div><label for="priority">Prioridade</label><select id="priority">${['Baixa','Média','Alta','Crítica'].map(s=>`<option ${s===a.priority?'selected':''}>${s}</option>`).join('')}</select></div></div><label for="response">Resposta para revisão</label><textarea id="response" maxlength="20000">${esc(a.response)}</textarea><h4>Fontes recuperadas</h4>${a.sources.length?a.sources.map(s=>`<details class="source"><summary>${esc(s.title)} · documento #${s.id}</summary><p>${esc(s.excerpt)}</p></details>`).join(''):'<p class="muted">Nenhuma fonte relevante encontrada. Revise a sugestão com atenção.</p>'}${a.review==='pending'?'<div class="actions"><button class="primary" id="approve">Aprovar e registrar resposta</button><button id="reject">Rejeitar sugestão</button></div>':`<p class="muted">Sugestão ${a.review==='approved'?'aprovada':'rejeitada'}. A resposta aprovada está no histórico.</p>`}<p class="muted">A resposta é registrada localmente; não há envio de e-mail nesta versão.</p></div>`:''}<h3>Comentários e histórico</h3><form id="comment-form"><label for="comment-author">Seu nome</label><input id="comment-author" required minlength="2" maxlength="180" value="${esc(t.assignee)}" placeholder="Quem está registrando?"><label for="comment-content">Comentário de atendimento</label><textarea id="comment-content" required maxlength="10000" placeholder="Registre tentativas, informações recebidas ou próximos passos."></textarea><button class="primary" type="submit">Adicionar comentário</button><p class="muted">Comentário visível ao solicitante. O autor é identificado pela conta autenticada.</p></form>${t.events.map(e=>historyEvent(t,e)).join('')}`);
 if($('#related-back'))$('#related-back').onclick=()=>openTicket(fromId).catch(error);
 if(isStaff()){$('#similar-resolved').onchange=()=>loadSimilar(id);loadSimilar(id);}else{$('.similar-panel').remove();}
 wireAttachments(t);
 document.querySelectorAll('[data-solution]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{const doc=await api(`/tickets/${id}/solutions/${b.dataset.solution}/article`,'POST');newDocument(doc,id);}catch(err){error(err);b.disabled=false;}});
 $('#assignee').setAttribute('list','assignees');
 $('#assignment-form').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{await api(`/tickets/${id}/assignment`,'PATCH',{assignee:$('#assignee').value,priority:$('#ticket-priority').value});await refresh();await openTicket(id);}catch(err){error(err);b.disabled=false;}};
 $('#comment-form').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{await api(`/tickets/${id}/comments`,'POST',{author:$('#comment-author').value,content:$('#comment-content').value});if(e.target.isConnected&&$('#modal').open)await openTicket(id);}catch(err){error(err);b.disabled=false;}};
 $('#status').onchange=async e=>{try{await api(`/tickets/${id}/status`,'PATCH',{status:e.target.value});await refresh();await openTicket(id);}catch(err){error(err);}};
 $('#analyze').onclick=async e=>{const b=e.target;b.disabled=true;b.textContent='Analisando no seu computador…';try{await api(`/tickets/${id}/analyze`,'POST');await openTicket(id);}catch(err){error(err);b.disabled=false;b.textContent='Tentar análise novamente';}};
 async function review(decision){const buttons=[$('#approve'),$('#reject')];buttons.forEach(b=>b.disabled=true);try{await api(`/tickets/${id}/review`,'POST',{decision,response:$('#response').value,category:$('#category').value,priority:$('#priority').value});await refresh();await openTicket(id);}catch(err){error(err);buttons.forEach(b=>b.disabled=false);}}
 if($('#approve')){$('#approve').onclick=()=>review('approved');$('#reject').onclick=()=>review('rejected');}
 $('#comment-author').value=currentUser.name;$('#comment-author').readOnly=true;
 if(!isStaff()){$('#assignment-form').nextElementSibling.remove();$('#assignment-form').remove();$('#status').disabled=true;const group=$('#analyze').parentElement;group.nextElementSibling.remove();group.remove();}
}
async function loadDocuments(){
 const q=$('#doc-search').value.trim();
 documentCache=await api('/documents?q='+encodeURIComponent(q)+'&category='+encodeURIComponent(docCategory));
 $('#doc-count').textContent=documentCache.length;
 $('#doc-categories').innerHTML=['Todas',...categories].map(c=>`<button data-category="${c==='Todas'?'':c}" class="${(docCategory||'Todas')===c?'selected':''}" aria-pressed="${(docCategory||'Todas')===c}">${c}</button>`).join('');
 document.querySelectorAll('[data-category]').forEach(b=>b.onclick=()=>{docCategory=b.dataset.category;loadDocuments().catch(error);});
 $('#documents').innerHTML=documentCache.length?documentCache.map(d=>`<article class="panel doc-card"><div class="doc-card-top"><span class="doc-icon">▧</span>${badge(d.category)}${d.status==='draft'?'<span class="draft-badge">Rascunho</span>':''}</div><h2><button class="article-title" data-read="${d.id}">${esc(d.title)}</button></h2><p class="doc-preview">${esc(d.content.slice(0,180))}…</p><div class="tags">${d.tags.split(',').filter(t=>t.trim()).map(tag=>`<span>${esc(tag.trim())}</span>`).join('')}</div><div class="doc-footer"><small>Atualizado ${date(d.updated_at||d.created_at)}</small><button data-read="${d.id}" class="subtle">Ler artigo ↗</button></div></article>`).join(''):'<div class="panel doc-card"><h2>Nenhum artigo por aqui</h2><p>Tente outra busca ou adicione um procedimento à biblioteca.</p></div>';
 document.querySelectorAll('[data-read]').forEach(b=>b.onclick=()=>readDocument(Number(b.dataset.read)));
}
function readDocument(id){
 const d=documentCache.find(d=>d.id===id);if(!d)return;
 modal(d.title,`<div class="detail-meta">${badge(d.category)}<span class="muted">Documento #${d.id} · ${date(d.updated_at||d.created_at)}</span></div>${d.status==='draft'?'<p class="draft-notice">Este rascunho ainda não é consultado pela IA. Revise o conteúdo e publique quando estiver pronto.</p>':''}${d.source_ticket_id?`<p class="muted">Origem: chamado #${d.source_ticket_id}</p>`:''}<div class="article-body">${esc(d.content)}</div><div class="actions"><button class="primary" id="edit-document">Editar artigo</button><button id="delete-document" class="danger">Excluir artigo</button></div>`);
 if(!isStaff()){$('#edit-document').parentElement.remove();return;}
 $('#edit-document').onclick=()=>newDocument(d);
 if(currentUser.role!=='admin'){$('#delete-document').remove();return;}
 $('#delete-document').onclick=async()=>{if(!confirm('Excluir este artigo da base de conhecimento?'))return;try{await api('/documents/'+id,'DELETE');$('#modal').close();await loadDocuments();}catch(err){error(err);}};
}
let searchTimer;$('#doc-search').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>loadDocuments().catch(error),250);};
function newDocument(doc=null,returnTicket=null){
 modal(doc?'Editar artigo':'Adicionar conhecimento',`<form id="doc-form"><label for="doc-title">Título do artigo</label><input id="doc-title" name="title" required minlength="3" maxlength="180" value="${esc(doc?.title||'')}" placeholder="Ex.: Recuperar acesso ao sistema"><div class="editor-meta"><div><label for="doc-category">Categoria</label><select id="doc-category" name="category">${categories.map(c=>`<option ${c===(doc?.category||'Geral')?'selected':''}>${c}</option>`).join('')}</select></div><div><label for="doc-tags">Etiquetas separadas por vírgula</label><input id="doc-tags" name="tags" maxlength="300" value="${esc(doc?.tags||'')}" placeholder="login, senha, acesso"></div></div><label for="content">Procedimento em texto</label><textarea id="content" name="content" required minlength="20" maxlength="100000" placeholder="Descreva o objetivo, os passos autorizados e quando escalar o problema." style="min-height:300px">${esc(doc?.content||'')}</textarea><label for="doc-status">Disponibilidade na base</label><select id="doc-status" name="status"><option value="draft" ${doc?.status==='draft'?'selected':''}>Rascunho — fora da busca da IA</option><option value="published" ${doc?.status!=='draft'?'selected':''}>Publicado — disponível para a IA</option></select><p class="muted">Antes de publicar, confirme que o procedimento resolveu o problema e remova nomes, e-mails, credenciais e informações específicas do solicitante.</p><div class="actions"><button class="primary">${doc?'Salvar artigo':'Salvar na biblioteca'}</button></div></form>`);
 $('#doc-form').onsubmit=async e=>{e.preventDefault();const button=e.submitter;button.disabled=true;try{await api('/documents'+(doc?'/'+doc.id:''),doc?'PUT':'POST',Object.fromEntries(new FormData(e.target)));if(returnTicket){await openTicket(returnTicket);}else{$('#modal').close();await loadDocuments();}}catch(err){error(err);button.disabled=false;}};
}
$('#sort').onchange=renderTickets;
$('#clear-filters').onclick=()=>{$('#search').value='';['filter','owner-filter','sla-filter'].forEach(id=>$('#'+id).value='');document.querySelectorAll('[data-queue]').forEach(b=>{b.classList.toggle('selected',b.dataset.queue==='all');b.setAttribute('aria-pressed',b.dataset.queue==='all');});renderTickets();};
document.querySelectorAll('[data-queue]').forEach(b=>b.onclick=()=>{$('#filter').value='';$('#owner-filter').value=b.dataset.queue==='unassigned'?'unassigned':'';$('#sla-filter').value=b.dataset.queue==='overdue'?'overdue':'';document.querySelectorAll('[data-queue]').forEach(n=>{n.classList.toggle('selected',n===b);n.setAttribute('aria-pressed',n===b);});renderTickets();});
function switchView(next){
 view=next;
 document.querySelectorAll('.nav').forEach(n=>n.classList.toggle('active',n.dataset.view===view));
 ['tickets','documents','metrics','users'].forEach(name=>$('#'+name+'-view').hidden=view!==name);
 const titles={users:['Cada pessoa, seu espaço.','Usuários','Acessos organizados para uma equipe em sintonia.'],tickets:['Seu suporte, em sintonia.','Chamados','Cada chamado no lugar certo. Cada solução com contexto.'],documents:['Conhecimento que conecta.','Documentação','O que a equipe aprende vira o próximo passo de alguém.'],metrics:['Resultados que orientam.','Indicadores','Entenda a demanda. Encontre gargalos. Acompanhe a evolução.']};
 $('#page-title').textContent=titles[view][0];$('#breadcrumb').textContent=titles[view][1];$('#subtitle').textContent=titles[view][2];
 $('#create').hidden=view==='metrics'||(view==='documents'&&!isStaff());$('#create').textContent=view==='users'?'+ Novo usuário':view==='documents'?'+ Novo artigo':'+ Novo chamado';
 if(view==='documents')loadDocuments().catch(error);
 if(view==='metrics')loadMetrics();
 if(view==='users')loadUsers().catch(error);
}
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>switchView(b.dataset.view));
$('#create').onclick=()=>view==='users'?editUser():view==='documents'?newDocument():newTicket();
async function health(){try{const h=await api('/health');$('#health').classList.toggle('offline',!h.online);$('#health').textContent=h.online?`● IA local conectada · ${h.model} · Revisão humana ativa`:`○ IA local indisponível · Inicie o Ollama e instale ${h.model}. Chamados e documentação continuam disponíveis.`;}catch(err){error(err);}}
setInterval(()=>{if(currentUser)health();},30000);

setInterval(()=>{if(currentUser)refresh().catch(error);},60000);

function attachmentPanel(t){
 return `<section class="attachment-panel"><div class="attachment-heading"><h3>Anexos <span class="count">${t.attachments.length}</span></h3><span class="muted">Armazenamento local</span></div><form id="attachment-form"><label for="attachment-file">Adicionar evidência</label><input id="attachment-file" type="file" required accept=".png,.jpg,.jpeg,.webp,.pdf,.txt,.log,.csv"><button type="submit">Enviar anexo</button><p class="muted">PNG, JPG, WebP, PDF, TXT, LOG e CSV · Até 10 MB por arquivo, 20 por chamado. Os anexos não são lidos pela IA.</p></form><div class="attachment-list">${t.attachments.map(a=>`<div class="attachment-row"><div><a href="/api/tickets/${t.id}/attachments/${a.id}" download>${esc(a.filename)}</a><small>${formatBytes(a.size)} · ${date(a.created_at)}</small></div><button type="button" data-remove-attachment="${a.id}" class="subtle danger" aria-label="Remover ${esc(a.filename)}">Remover</button></div>`).join('')||'<p class="muted">Nenhum anexo neste chamado.</p>'}</div></section>`;
}
function formatBytes(size){return size<1024?size+' B':size<1048576?(size/1024).toFixed(1)+' KB':(size/1048576).toFixed(1)+' MB';}
function wireAttachments(t){
 $('#attachment-form').onsubmit=async e=>{e.preventDefault();const file=$('#attachment-file').files[0];if(!file)return;if(file.size>10*1024*1024){error(new Error('O anexo excede o limite de 10 MB.'));return;}const b=e.submitter;b.disabled=true;b.textContent='Enviando…';try{const result=await fetch(`/api/tickets/${t.id}/attachments?filename=${encodeURIComponent(file.name)}`,{method:'POST',headers:{'X-CSRF-Token':csrfToken},body:file});const data=await result.json();if(result.status===401)showLogin('Sua sessão terminou. Entre novamente.');if(!result.ok)throw new Error(typeof data.detail==='string'?data.detail:'Não foi possível enviar o anexo.');await openTicket(t.id);}catch(err){error(err);b.disabled=false;b.textContent='Enviar anexo';}};
 document.querySelectorAll('[data-remove-attachment]').forEach(b=>{const attachment=t.attachments.find(a=>a.id===Number(b.dataset.removeAttachment));if(!isStaff()&&attachment.uploader_id!==currentUser.id)b.remove();});
 document.querySelectorAll('[data-remove-attachment]').forEach(b=>b.onclick=async()=>{if(!confirm('Remover este anexo do chamado?'))return;b.disabled=true;try{await api(`/tickets/${t.id}/attachments/${b.dataset.removeAttachment}`,'DELETE');await openTicket(t.id);}catch(err){error(err);b.disabled=false;}});
}
function historyEvent(t,e){
 const labels={approved:'Resposta aprovada',rejected:'Revisão',created:'Abertura',status:'Status',analysis:'IA local',comment:'Comentário',assignment:'Responsável',priority:'Prioridade',attachment:'Anexo',attachment_removed:'Anexo removido',article:'Conhecimento'};
 const article=t.articles.find(d=>d.source_event_id===e.id);
 return `<div class="event"><small>${date(e.created_at)} · ${esc(labels[e.kind]||e.kind)}${e.author?' · '+esc(e.author):''}</small><p>${esc(e.content)}</p>${isStaff()&&e.kind==='approved'&&t.status==='Resolvido'?`<button class="solution-article" data-solution="${e.id}">▧ ${article?'Revisar artigo #'+article.id:'Transformar solução em artigo'}</button>`:''}</div>`;
}

let similarRequest=0;
async function loadSimilar(id){
 const request=++similarRequest, box=$('#similar-results'), only=$('#similar-resolved').checked;
 box.textContent='Buscando casos anteriores…';
 try{
  const rows=await api(`/tickets/${id}/similar?resolved_only=${only}`);
  if(request!==similarRequest||currentId!==id||!box.isConnected)return;
  box.innerHTML=rows.length?rows.map(t=>`<article class="similar-card"><div><button class="similar-title" data-related="${t.id}">#${t.id} · ${esc(t.title)}</button>${badge(t.status)}</div><p class="similar-match">Afinidade textual ${t.score}% · Termos: ${esc(t.matched_terms.join(', '))}</p>${t.solution?`<details><summary>Consultar resposta aprovada</summary><p class="similar-solution">${esc(t.solution)}</p></details>`:t.status==='Resolvido'?'<p class="muted">Sem resposta aprovada registrada.</p>':''}</article>`).join(''):'<p class="muted">Nenhum chamado semelhante encontrado com os termos disponíveis.</p>';
  box.querySelectorAll('[data-related]').forEach(b=>b.onclick=()=>openTicket(Number(b.dataset.related),id).catch(error));
 }catch(err){if(box.isConnected)box.textContent='Não foi possível buscar casos semelhantes. '+err.message;}
}
let metricsRequest=0;
function durationLabel(seconds){if(seconds===null)return '—';if(seconds<60)return '< 1 min';if(seconds<3600)return Math.round(seconds/60)+' min';return (seconds/3600).toLocaleString('pt-BR',{maximumFractionDigits:1})+' h';}
function metricBars(values){const entries=Object.entries(values).sort((a,b)=>b[1]-a[1]),max=Math.max(1,...entries.map(e=>e[1]));return entries.length?entries.map(([label,count])=>`<div class="metric-bar-row"><div><span>${esc(label)}</span><strong>${count}</strong></div><div class="metric-track"><span style="width:${count/max*100}%"></span></div></div>`).join(''):'<p class="muted">Nenhum dado neste período.</p>';}
async function loadMetrics(){
 const request=++metricsRequest,box=$('#metrics-content');box.setAttribute('aria-busy','true');
 try{
  const m=await api('/metrics?days='+$('#metrics-period').value);
  if(request!==metricsRequest)return;
  const cards=[['Chamados no período',m.total,'Abertos no intervalo selecionado'],['Pendentes',m.open,`${m.unassigned} sem responsável`],['SLA atrasado',m.overdue,`${m.warning} próximos do vencimento`],['Resolvidos',m.resolved,'Situação atual dos chamados'],['Tempo médio de resolução',durationLabel(m.average_resolution_seconds),'Da abertura até a última resolução'],['Resolvidos dentro do SLA',m.sla_met_percent===null?'—':m.sla_met_percent.toLocaleString('pt-BR')+'%','Entre os chamados resolvidos'],['Chamados reabertos',m.reopened_tickets,`${m.reopening_events} reabertura(s) no histórico desses chamados`]];
  const max=Math.max(1,...m.trend.map(d=>d.opened));
  box.innerHTML=`${!m.total?'<div class="metrics-empty">Ainda não há chamados neste período. Selecione outro intervalo ou crie o primeiro chamado.</div>':''}<div class="metric-cards">${cards.map(([label,value,note])=>`<article class="stat"><p>${label}</p><strong>${value}</strong><span class="metric-note">${note}</span></article>`).join('')}</div><div class="metric-charts"><section class="panel metric-chart"><h3>Volume por categoria</h3>${metricBars(m.by_category)}</section><section class="panel metric-chart"><h3>Distribuição por status</h3>${metricBars(m.by_status)}</section><section class="panel metric-chart"><h3>Prioridade dos chamados</h3>${metricBars(m.by_priority)}</section><section class="panel metric-chart trend-chart"><h3>Entradas nos últimos ${m.trend.length} dias</h3><div class="trend-bars" role="img" aria-label="${esc(m.trend.map(d=>d.date+': '+d.opened+' chamado(s)').join('; '))}">${m.trend.map(d=>`<div class="trend-column" title="${d.date}: ${d.opened} chamado(s)"><span>${d.opened}</span><div class="trend-track"><i style="height:${d.opened/max*100}%"></i></div><small>${d.date.slice(8)}/${d.date.slice(5,7)}</small></div>`).join('')}</div></section></div><p class="metrics-caption">Atualizado em ${date(m.as_of)}. Sem resoluções no período, médias e percentuais aparecem como “—”. Reaberturas contam as transições registradas após uma resolução.</p>`;
 }catch(err){if(request===metricsRequest)box.innerHTML=`<p class="metrics-empty" role="alert">Não foi possível carregar os indicadores: ${esc(err.message)}</p>`;}
 finally{if(request===metricsRequest)box.setAttribute('aria-busy','false');}
}
$('#metrics-period').onchange=loadMetrics;$('#metrics-refresh').onclick=loadMetrics;
setInterval(()=>{if(currentUser&&view==='metrics')loadMetrics();},60000);
