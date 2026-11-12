/* Standalone portfolio simulation. This is not authentication or a production API. */
(() => {
  const storageKey='orbita-pages-v1', realFetch=window.fetch.bind(window);
  const stamp=()=>new Date().toISOString();
  const ago=hours=>new Date(Date.now()-hours*3600000).toISOString();
  const roles=['requester','agent','admin'];
  const hours={Baixa:72,'Média':24,Alta:8,'Crítica':2};
  const users=[
    {id:1,name:'Solicitante Demo',email:'solicitante@orbita.local',role:'requester',active:1,password:'Orbita@Solicitante123'},
    {id:2,name:'Atendente Demo',email:'atendente@orbita.local',role:'agent',active:1,password:'Orbita@Atendente123'},
    {id:3,name:'Administrador Demo',email:'admin@orbita.local',role:'admin',active:1,password:'Orbita@Admin123'}
  ];
  function initial(){return {users,documents:structuredClone(window.ORBITA_DEMO_ARTICLES),tickets:[
    {id:1,title:'VPN sem conexão no trabalho remoto',description:'O cliente VPN apresenta erro de conexão. Uma pessoa afetada no acesso remoto.',requester:'Solicitante Demo',requester_id:1,status:'Resolvido',category:'Rede',priority:'Média',assignee:'Atendente Demo',analysis:null,created_at:ago(48),resolved_at:ago(46)},
    {id:2,title:'VPN com erro de conexão',description:'O cliente VPN não conecta ao acesso remoto desde o início do expediente.',requester:'Solicitante Demo',requester_id:1,status:'Aberto',category:'Rede',priority:'Alta',assignee:'',analysis:null,created_at:ago(10),resolved_at:null},
    {id:3,title:'Solicitação de acesso ao portal',description:'Preciso de orientação para recuperar o acesso ao portal interno.',requester:'Pessoa fictícia',requester_id:99,status:'Em análise',category:'Acesso',priority:'Média',assignee:'Atendente Demo',analysis:null,created_at:ago(4),resolved_at:null}
  ],events:[{id:1,ticket_id:1,kind:'approved',author:'Atendente Demo',content:'Exemplo fictício: o acesso foi restabelecido após seguir o procedimento oficial da equipe de redes. Confirme a mensagem de erro e consulte o procedimento da sua organização antes de agir.',created_at:ago(46)}]};}
  let state;
  try{state=JSON.parse(localStorage.getItem(storageKey))||initial();}catch{state=initial();}
  const save=()=>localStorage.setItem(storageKey,JSON.stringify(state));
  const next=rows=>Math.max(0,...rows.map(r=>r.id))+1;
  const publicUser=u=>{const {password,...result}=u;return result;};
  const current=()=>state.users.find(u=>u.id===Number(sessionStorage.getItem('orbita-demo-user'))&&u.active);
  const event=(id,kind,content)=>state.events.push({id:next(state.events),ticket_id:id,kind,content,created_at:stamp(),author:current().name});
  const fail=(message,status=403)=>{throw {message,status};};
  function sla(t){const due=new Date(t.created_at).getTime()+hours[t.priority]*3600000,seconds=(due-(t.resolved_at?new Date(t.resolved_at).getTime():Date.now()))/1000;return {due_at:new Date(due).toISOString(),hours:hours[t.priority],remaining_seconds:Math.round(seconds),state:t.status==='Resolvido'?(seconds>=0?'met':'breached'):seconds<0?'overdue':seconds<Math.min(hours[t.priority]*.2,2)*3600?'warning':'on_track'};}
  const ticketView=t=>({...t,sla:sla(t)});
  const terms=text=>new Set(text.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').match(/[a-z0-9]{3,}/g)||[]);
  function dashboard(days){
    const start=days?new Date(Date.now()-(days-1)*86400000):null;
    if(start)start.setHours(0,0,0,0);
    const rows=state.tickets.filter(t=>!start||new Date(t.created_at)>=start),resolved=rows.filter(t=>t.status==='Resolvido');
    const group=field=>rows.reduce((m,t)=>(m[t[field]]=(m[t[field]]||0)+1,m),{});
    const trend=Array.from({length:Math.min(days||14,14)},(_,i)=>{const d=new Date();d.setDate(d.getDate()-(Math.min(days||14,14)-1-i));const date=d.toLocaleDateString('en-CA');return {date,opened:rows.filter(t=>new Date(t.created_at).toLocaleDateString('en-CA')===date).length};});
    const reopened=new Set(), previous={};let count=0;
    state.events.filter(e=>e.kind==='status'&&rows.some(t=>t.id===e.ticket_id)).forEach(e=>{const status=e.content.replace('Status alterado para ','');if(previous[e.ticket_id]==='Resolvido'&&status!=='Resolvido'){reopened.add(e.ticket_id);count++;}previous[e.ticket_id]=status;});
    return {total:rows.length,open:rows.length-resolved.length,resolved:resolved.length,overdue:rows.filter(t=>sla(t).state==='overdue').length,warning:rows.filter(t=>sla(t).state==='warning').length,unassigned:rows.filter(t=>!t.assignee&&t.status!=='Resolvido').length,average_resolution_seconds:resolved.length?resolved.reduce((n,t)=>n+(new Date(t.resolved_at)-new Date(t.created_at))/1000,0)/resolved.length:null,sla_met_percent:resolved.length?Math.round(resolved.filter(t=>sla(t).state==='met').length/resolved.length*100):null,reopened_tickets:reopened.size,reopening_events:count,by_category:group('category'),by_status:group('status'),by_priority:group('priority'),trend,as_of:stamp()};
  }
  async function route(path,method,body,query){
    if(path==='/auth/login'){
      const user=state.users.find(u=>u.email===body.email.trim().toLowerCase()&&u.password===body.password&&u.active);
      if(!user)fail('E-mail ou senha inválidos nesta demonstração.',401);
      sessionStorage.setItem('orbita-demo-user',user.id);return {user:publicUser(user),csrf:'demo'};
    }
    const user=current();if(!user)fail('Entre na demonstração para continuar.',401);
    const staff=user.role!=='requester';
    if(path==='/auth/me')return {user:publicUser(user),csrf:'demo'};
    if(path==='/auth/logout'){sessionStorage.removeItem('orbita-demo-user');return {ok:true};}
    if(path==='/auth/password')fail('Troca de senha disponível na instalação local. A demonstração usa acessos públicos.');
    if(path==='/health')return {online:false,model:'IA disponível na instalação local',models:[]};
    if(path==='/metrics'){if(!staff)fail('Recurso da equipe de suporte.');return dashboard(Number(query.get('days')??30));}
    if(path.startsWith('/users')){
      if(user.role!=='admin')fail('Recurso de administrador.');
      if(method==='GET')return state.users.map(publicUser);
      if(method==='POST'){if(state.users.some(u=>u.email===body.email))fail('E-mail já cadastrado.',409);const u={...body,id:next(state.users)};state.users.push(u);return publicUser(u);}
      const u=state.users.find(u=>u.id===Number(path.split('/')[2]));if(!u)fail('Usuário não encontrado.',404);
      if(u.id===3&&(body.role!=='admin'||!body.active))fail('Mantenha o administrador da demonstração ativo.',409);
      Object.assign(u,{...body,password:body.password||u.password});return {ok:true};
    }
    if(path==='/documents'&&method==='GET')return state.documents.filter(d=>(staff||d.status==='published')&&(!query.get('category')||d.category===query.get('category'))&&(!query.get('q')||[...terms(query.get('q'))].some(term=>terms(d.title+' '+d.content+' '+d.tags).has(term))));
    if(path.startsWith('/documents')){
      if(!staff)fail('Recurso da equipe de suporte.');
      if(method==='POST'){const d={...body,id:next(state.documents),created_at:stamp(),updated_at:stamp()};state.documents.unshift(d);return {id:d.id};}
      const d=state.documents.find(d=>d.id===Number(path.split('/')[2]));if(!d)fail('Artigo não encontrado.',404);
      if(method==='PUT'){Object.assign(d,body,{updated_at:stamp()});return {ok:true};}
      if(method==='DELETE'){if(user.role!=='admin')fail('Recurso de administrador.');state.documents=state.documents.filter(row=>row.id!==d.id);return {ok:true};}
    }
    if(path==='/tickets'){
      if(method==='GET')return state.tickets.filter(t=>staff||t.requester_id===user.id).map(ticketView).reverse();
      if(method==='POST'){const t={...body,id:next(state.tickets),requester:staff?body.requester:user.name,requester_id:user.id,status:'Aberto',category:'Não classificado',priority:'Média',assignee:'',analysis:null,created_at:stamp(),resolved_at:null};state.tickets.push(t);event(t.id,'created','Chamado criado na demonstração.');return ticketView(t);}
    }
    const match=path.match(/^\/tickets\/(\d+)(.*)$/);if(!match)fail('Recurso não disponível na demonstração.',404);
    const t=state.tickets.find(t=>t.id===Number(match[1])),action=match[2];if(!t||(!staff&&t.requester_id!==user.id))fail('Chamado não encontrado.',404);
    if(!action&&method==='GET')return {...ticketView(t),analysis:staff?t.analysis:null,attachments:[],articles:staff?state.documents.filter(d=>d.source_ticket_id===t.id):[],events:state.events.filter(e=>e.ticket_id===t.id).slice().reverse()};
    if(action==='/comments'){event(t.id,'comment',body.content);return {ok:true};}
    if(action.startsWith('/attachments'))fail('Anexos exigem o backend da instalação local. Nenhum arquivo foi enviado.',503);
    if(!staff)fail('Recurso da equipe de suporte.');
    if(action==='/analyze')fail('O GitHub Pages não executa Ollama. Use a instalação local para gerar análises reais.',503);
    if(action==='/status'){t.status=body.status;t.resolved_at=body.status==='Resolvido'?stamp():null;event(t.id,'status','Status alterado para '+body.status);return {ok:true};}
    if(action==='/assignment'){Object.assign(t,body);event(t.id,'assignment','Responsável: '+(body.assignee||'Não atribuído'));return ticketView(t);}
    if(action==='/similar'){
      const source=terms(t.title+' '+t.description);
      return state.tickets.filter(r=>r.id!==t.id&&(query.get('resolved_only')!=='true'||r.status==='Resolvido')).map(r=>{const common=[...terms(r.title+' '+r.description)].filter(term=>source.has(term)),solution=state.events.filter(e=>e.ticket_id===r.id&&e.kind==='approved').at(-1);return {...r,matched_terms:common.slice(0,8),score:Math.round(common.length/Math.max(source.size,1)*100),solution:r.status==='Resolvido'?solution?.content:null};}).filter(r=>r.score>=15).sort((a,b)=>b.score-a.score).slice(0,5);
    }
    if(action.match(/^\/solutions\/\d+\/article$/)){
      if(t.status!=='Resolvido')fail('Resolva o chamado antes de criar um artigo.',409);
      const id=Number(action.split('/')[2]),solution=state.events.find(e=>e.id===id&&e.ticket_id===t.id&&e.kind==='approved');if(!solution)fail('Resposta aprovada não encontrada.',404);
      let d=state.documents.find(d=>d.source_event_id===id);if(d)return d;
      d={id:next(state.documents),title:t.title,content:'Objetivo\nRevise quando o procedimento se aplica.\n\nSolução aprovada\n'+solution.content,category:t.category==='Não classificado'?'Geral':t.category,tags:'',status:'draft',source_ticket_id:t.id,source_event_id:id,created_at:stamp(),updated_at:stamp()};state.documents.unshift(d);event(t.id,'article','Rascunho de demonstração criado.');return d;
    }
    fail('Ação disponível na versão local.',503);
  }
  window.fetch=async(input,options={})=>{
    const url=new URL(typeof input==='string'?input:input.url,location.href),index=url.pathname.indexOf('/api/');
    if(index<0)return realFetch(input,options);
    try{const data=await route(url.pathname.slice(index+4),options.method||'GET',typeof options.body==='string'?JSON.parse(options.body):{},url.searchParams);save();return new Response(JSON.stringify(data),{headers:{'Content-Type':'application/json'}});}
    catch(error){return new Response(JSON.stringify({detail:error.message||'Não foi possível concluir na demonstração.'}),{status:error.status||500,headers:{'Content-Type':'application/json'}});}
  };
})();
