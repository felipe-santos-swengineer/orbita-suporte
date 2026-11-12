"""Starter triage guides. Adapt to the organization's approved procedures."""
ARTICLES = [
    ('Falha no login: primeiros passos', 'Acesso', 'login, senha, autenticação, acesso', '''Objetivo: coletar informações para investigar falhas de acesso.

1. Registre o nome do sistema e a mensagem exata apresentada, sem incluir senhas ou códigos de autenticação.
2. Confirme se o erro afeta somente uma pessoa ou outros usuários.
3. Verifique se há comunicado interno de indisponibilidade antes de orientar novas tentativas.
4. Se a senha foi esquecida, use somente o fluxo oficial de recuperação do sistema. Nunca solicite a senha do usuário.
5. Se houver bloqueio de conta ou erro de permissão, encaminhe ao responsável por identidades com o horário do erro e o identificador da conta.

Escalonar quando: múltiplos usuários estiverem sem acesso, houver suspeita de acesso indevido ou a recuperação oficial falhar.
Guia inicial: valide os canais e responsáveis da sua organização antes de aplicar.'''),
    ('VPN sem conexão: roteiro de triagem', 'Rede', 'vpn, conexão, remoto, erro', '''Objetivo: reunir evidências de falha no acesso remoto.

1. Solicite a mensagem ou código de erro da VPN e o horário da ocorrência.
2. Confirme se outros serviços de internet funcionam e se outros usuários também foram afetados.
3. Registre o nome e a versão do cliente VPN, o sistema operacional e a rede utilizada.
4. Consulte os comunicados de manutenção e o procedimento oficial de acesso remoto.
5. Encaminhe as evidências ao time de redes se a falha persistir.

Não desative firewall, antivírus ou validação de certificados para contornar o problema. Não sugira VPNs de terceiros.
Guia inicial: adapte às ferramentas e políticas autorizadas.'''),
    ('Computador lento: informações para diagnóstico', 'Hardware', 'computador, lento, memória, desempenho', '''Objetivo: identificar o alcance e a frequência da lentidão.

1. Pergunte quando a lentidão começou e se ocorre em todos os aplicativos ou em apenas um.
2. Registre o modelo do equipamento, o sistema operacional e as atividades afetadas.
3. Peça ao usuário que salve o trabalho antes de qualquer ação que possa fechar aplicativos.
4. Se permitido pela política interna, consulte os indicadores de CPU, memória e disco no gerenciador de tarefas, sem encerrar processos desconhecidos.
5. Registre alterações recentes e encaminhe os dados à equipe responsável.

Não apague arquivos nem instale ferramentas de limpeza sem procedimento aprovado.
Guia inicial: não substitui o diagnóstico técnico do equipamento.'''),
    ('Aplicativo com erro ou travamento', 'Software', 'aplicativo, software, erro, travamento', '''Objetivo: obter um relato reproduzível para investigar falhas de software.

1. Registre aplicativo, versão, sistema operacional e mensagem exata de erro.
2. Solicite os passos que levam ao problema, o horário e a frequência.
3. Confirme o impacto: usuário único, equipe ou serviço inteiro.
4. Antes de fechar o aplicativo, verifique se há trabalho não salvo.
5. Consulte problemas conhecidos na documentação interna e encaminhe evidências ao responsável pelo sistema.

Não solicite bases de dados, arquivos confidenciais ou logs completos sem avaliar dados sensíveis.
Guia inicial: procedimentos de reinstalação exigem validação interna.'''),
    ('Impressora indisponível: coleta de evidências', 'Hardware', 'impressora, impressão, fila, papel', '''Objetivo: distinguir falha do equipamento, da conexão ou da estação.

1. Registre o nome da impressora e a mensagem exibida no computador ou no painel do equipamento.
2. Confirme se o problema afeta outros usuários e se a impressora está ligada.
3. Verifique visualmente indicadores de falta de papel ou suprimento, sem abrir partes restritas do equipamento.
4. Informe se o trabalho aparece na fila e quando o problema começou.
5. Encaminhe ao suporte responsável com o local e a identificação do equipamento.

Não exclua trabalhos de outros usuários nem instale drivers de fontes não aprovadas.
Guia inicial: siga o procedimento do fabricante e da organização.'''),
    ('Como definir prioridade e registrar impacto', 'Processos', 'prioridade, urgência, impacto, sla, chamado', '''Objetivo: classificar o atendimento com base em evidências.

Crítica: interrupção abrangente de serviço essencial, com impacto grave confirmado. SLA de resolução da central: 2 horas corridas.
Alta: atividade importante ou equipe bloqueada. SLA: 8 horas corridas.
Média: problema com impacto limitado que requer atendimento. SLA: 24 horas corridas.
Baixa: solicitação sem interrupção relevante ou dúvida operacional. SLA: 72 horas corridas.

Registre quantidade de pessoas afetadas, atividade impedida, início do problema e existência de alternativa temporária.
A urgência informada pelo solicitante deve ser avaliada junto ao impacto. O atendente confirma a prioridade.
Na central, aguardar usuário não pausa o SLA. Alterar prioridade recalcula o prazo desde a abertura.
Guia inicial: os prazos são regras desta aplicação e podem precisar de adaptação à operação.'''),
]
