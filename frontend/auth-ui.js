const roleNames={requester:'Solicitante',agent:'Atendente',admin:'Administrador'};
function showLogin(message=''){
 currentUser=null;csrfToken='';tickets=[];documentCache=[];currentId=null;ticketRequest++;metricsRequest++;similarRequest++;usersCache=[];
 if($('#modal').open)$('#modal').close();$('#modal-content').innerHTML='';$('#rows').innerHTML='';$('#documents').innerHTML='';$('#metrics-content').innerHTML='';$('#users-list').innerHTML='';
 document.body.classList.add('signed-out');$('#login-screen').hidden=false;$('#login-password').value='';$('#login-error').textContent=message;$('#login-error').hidden=!message;$('#notice').hidden=true;
}
async function enterWorkspace(data){
 currentUser=data.user;csrfToken=data.csrf;document.body.classList.remove('signed-out');$('#login-screen').hidden=true;
 $('#account-name').textContent=currentUser.name+' · '+roleNames[currentUser.role];
 $('[data-view="metrics"]').hidden=!isStaff();$('[data-view="users"]').hidden=currentUser.role!=='admin';
 $('#search').value='';['filter','owner-filter','sla-filter'].forEach(id=>$('#'+id).value='');$('#doc-search').value='';docCategory='';
 switchView('tickets');await refresh();health();
}
async function bootstrapAuth(){try{await enterWorkspace(await api('/auth/me'));}catch(err){showLogin();}}
$('#login-form').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;$('#login-error').hidden=true;try{await enterWorkspace(await api('/auth/login','POST',{email:$('#login-email').value,password:$('#login-password').value}));$('#login-password').value='';}catch(err){$('#login-error').textContent=err.message;$('#login-error').hidden=false;}finally{b.disabled=false;}};
$('#logout').onclick=async()=>{try{await api('/auth/logout','POST');showLogin();}catch(err){error(err);}};
$('#account-password').onclick=()=>{
 modal('Alterar minha senha',`<form id="password-form"><label for="old-password">Senha atual</label><input id="old-password" type="password" autocomplete="current-password" required maxlength="256"><label for="new-password">Nova senha</label><input id="new-password" type="password" autocomplete="new-password" required minlength="10" maxlength="256"><p class="muted">Use pelo menos 10 caracteres. Ao salvar, todas as suas sessões serão encerradas.</p><button class="primary">Salvar nova senha</button></form>`);
 $('#password-form').onsubmit=async e=>{e.preventDefault();e.submitter.disabled=true;try{await api('/auth/password','POST',{current_password:$('#old-password').value,new_password:$('#new-password').value});showLogin('Senha alterada. Entre com sua nova senha.');}catch(err){error(err);e.submitter.disabled=false;}};
};
let usersCache=[];
async function loadUsers(){usersCache=await api('/users');$('#users-list').innerHTML=usersCache.map(u=>`<article class="user-row"><div><strong>${esc(u.name)}</strong><span>${esc(u.email)}</span></div><div>${badge(roleNames[u.role])}${badge(u.active?'Ativo':'Desativado')}<button data-edit-user="${u.id}">Editar acesso</button></div></article>`).join('');document.querySelectorAll('[data-edit-user]').forEach(b=>b.onclick=()=>editUser(usersCache.find(u=>u.id===Number(b.dataset.editUser))));}
function editUser(user=null){
 modal(user?'Editar acesso':'Novo usuário',`<form id="user-form"><label for="user-name">Nome</label><input id="user-name" name="name" required minlength="2" maxlength="100" value="${esc(user?.name||'')}"><label for="user-email">E-mail</label><input id="user-email" name="email" type="email" required maxlength="180" value="${esc(user?.email||'')}"><label for="user-role">Papel</label><select id="user-role" name="role">${Object.entries(roleNames).map(([key,name])=>`<option value="${key}" ${user?.role===key?'selected':''}>${name}</option>`).join('')}</select><label for="user-password">${user?'Nova senha (opcional)':'Senha inicial'}</label><input id="user-password" name="password" type="password" autocomplete="new-password" minlength="10" maxlength="256" ${user?'':'required'}><label class="check-label user-active"><input id="user-active" type="checkbox" ${!user||user.active?'checked':''}> Acesso ativo</label><p class="muted">Alterar um usuário encerra suas sessões. O último administrador ativo não pode ser desativado.</p><button class="primary">Salvar acesso</button></form>`);
 $('#user-form').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;const body=Object.fromEntries(new FormData(e.target));body.active=$('#user-active').checked;try{await api('/users'+(user?'/'+user.id:''),user?'PUT':'POST',body);if(user?.id===currentUser.id){showLogin('Seu acesso foi atualizado. Entre novamente.');}else{$('#modal').close();await loadUsers();}}catch(err){error(err);b.disabled=false;}};
}
bootstrapAuth();
