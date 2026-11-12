# Órbita · Suporte em sintonia — V6

Central local para suporte: abertura e acompanhamento de chamados, base de conhecimento,
busca textual por trechos, sugestões com Ollama e revisão humana com histórico.
Frontend HTML/CSS/JavaScript, backend FastAPI e banco SQLite. Sem API paga e sem serviços externos no frontend.

## GitHub e demonstração online

- [Código no GitHub](https://github.com/felipe-santos-swengineer/orbita-suporte)
- [Demonstração no GitHub Pages](https://felipe-santos-swengineer.github.io/orbita-suporte/)

O Pages apresenta uma demonstração estática interativa, com dados fictícios e simulação dos três papéis.
As contas de demonstração abaixo também funcionam nessa versão. As alterações ficam somente no armazenamento
do navegador; **Restaurar demo** retorna aos exemplos iniciais. Não use dados ou senhas reais na demonstração.
O login do Pages é uma simulação de interface, não uma barreira de segurança.

A versão completa com autenticação no servidor, SQLite, anexos e Ollama precisa ser executada localmente.
GitHub Pages não executa Python nem hospeda o serviço Ollama. A demo informa essas limitações ao tentar analisar ou anexar.
Ela não se conecta ao seu computador nem publica seu banco, anexos, logs ou sessões.
Referência: [limitações de hospedagem do GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site).

O workflow `.github/workflows/pages.yml` publica automaticamente a demo a cada push na branch `main`.
Somente a pasta `dist/`, gerada com arquivos estáticos e exemplos fictícios, entra no artefato do Pages.
Para gerar e verificar localmente:

```powershell
python scripts/build_pages.py
python tests/pages_check.py
```

O teste visual requer Playwright e Microsoft Edge. O código completo do backend permanece no repositório.

## Login e contas de demonstração

Na primeira execução da V6, estas três contas de teste são criadas automaticamente:

| Papel | E-mail | Senha de teste |
|---|---|---|
| Solicitante | `solicitante@orbita.local` | `Orbita@Solicitante123` |
| Atendente | `atendente@orbita.local` | `Orbita@Atendente123` |
| Administrador | `admin@orbita.local` | `Orbita@Admin123` |

Abra http://127.0.0.1:8000 e entre com uma dessas contas. O cadastro é feito uma única vez;
reiniciar a aplicação não restaura senhas alteradas nem reativa contas desativadas.
As contas usam o mesmo banco, mas respeitam as permissões abaixo. Não há criação de chamados fictícios.

| Recurso | Solicitante | Atendente | Administrador |
|---|---|---|---|
| Criar e acompanhar chamados | Apenas os próprios | Todos | Todos |
| Comentar e baixar anexos | Nos próprios chamados | Todos | Todos |
| Enviar anexos | Nos próprios chamados | Todos | Todos |
| Remover anexos | Apenas os enviados por sua conta, em chamado próprio | Todos | Todos |
| Alterar status, prioridade e responsável | Não | Sim | Sim |
| Analisar com IA, revisar respostas e consultar semelhantes | Não | Sim | Sim |
| Ler artigos publicados | Sim | Sim | Sim |
| Ler rascunhos, criar, editar e publicar artigos | Não | Sim | Sim |
| Excluir artigos | Não | Não | Sim |
| Consultar indicadores | Não | Sim | Sim |
| Criar usuários, mudar papéis, redefinir senhas e desativar acessos | Não | Não | Sim |
| Alterar a própria senha | Sim | Sim | Sim |

### Roteiro de teste dos papéis

1. **Solicitante:** abra um chamado e adicione um comentário ou anexo. Você verá somente seus chamados,
   sem controles de atendimento e sem rascunhos da base. O nome do solicitante vem da conta autenticada.
2. Use **Sair** e entre como **Atendente**: abra o chamado criado, atribua o atendimento, atualize o status,
   gere uma análise local e revise a resposta. Confira também os indicadores e os artigos.
3. Entre como **Administrador**: abra **Usuários**, crie uma conta, edite o papel ou desative o acesso.
   Alterar um usuário encerra suas sessões. A aplicação impede desativar ou rebaixar o último administrador ativo.
4. Em qualquer conta, use **Minha senha** para alterá-la. Você deverá entrar novamente após a alteração.

Não há cadastro público, envio de e-mail ou recuperação de senha por e-mail. O administrador pode redefinir
a senha de outra conta em **Usuários → Editar acesso**. O responsável pelo atendimento ainda é preenchido por nome;
a identidade de quem comenta e executa ações no histórico vem da sessão, não desse campo.

### Sessões, permissões e migração

- As permissões são verificadas no backend, inclusive em downloads e requisições diretas à API.
- Chamados antigos sem proprietário continuam disponíveis para atendentes e administradores. Eles não são vinculados
  automaticamente a contas por coincidência de nome ou e-mail. Chamados novos são vinculados à conta que os cria.
- Solicitantes não recebem rascunhos da IA, eventos internos de análise nem artigos em rascunho.
- Comentários são visíveis ao solicitante do chamado; esta versão não possui notas internas separadas.
- Senhas são armazenadas com scrypt e salt individual. Sessões aleatórias são armazenadas por hash e expiram em 8 horas.
- O cookie é HttpOnly e SameSite=Strict. Escritas exigem token CSRF, e origens externas são bloqueadas.
- Após cinco falhas de login por conta e endereço em 15 minutos, novas tentativas são temporariamente bloqueadas.
- Logout, alteração de senha e edição/desativação de usuário invalidam as sessões correspondentes.

As senhas acima são públicas e destinadas à demonstração local. Antes de inserir dados reais, altere as senhas
ou desative as contas de teste, mantendo um administrador ativo. Continue executando em `127.0.0.1`.
Para um ambiente compartilhado, configure HTTPS e `COOKIE_SECURE=1`, além de revisar operação, backups e exposição do servidor.
Referências da implementação: [cookies de resposta no Starlette](https://starlette.dev/responses/) e
[scrypt na biblioteca padrão do Python](https://docs.python.org/3/library/hashlib.html#hashlib.scrypt).

## Novidades da V5

- Chamados semelhantes no detalhe de cada chamado: até cinco resultados, filtro de resolvidos, termos em comum e acesso ao caso completo com botão de volta.
- Casos resolvidos mostram a última resposta aprovada; casos reabertos não apresentam a resposta como uma solução concluída.
- Comparação textual local por TF-IDF, com mais peso no título e normalização de acentos. O percentual representa afinidade textual, não probabilidade de mesma causa ou confiança da IA.
- Aba **Indicadores** com filtros de 7, 30, 90 dias ou todo o histórico e atualização manual ou a cada minuto.
- Total, pendências, responsáveis ausentes, atrasos, resoluções, média de tempo de resolução, cumprimento de SLA e reaberturas.
- Gráficos de categoria, status, prioridade e entradas diárias dos últimos 7 ou 14 dias, conforme o período selecionado.

Os indicadores usam os chamados **criados no período**, com seu estado atual. O período começa à meia-noite
de Fortaleza (UTC−3), incluindo o dia atual. Não representam todas as resoluções ocorridas no intervalo,
pois um chamado criado antes dele fica fora desse recorte.
O tempo médio considera os chamados atualmente resolvidos, da criação à última resolução, incluindo esperas e reaberturas.
O percentual de SLA usa a prioridade atual e somente chamados resolvidos; sem resoluções, média e percentual ficam sem valor.
Reaberturas são identificadas por transições no histórico de status após uma resolução, contando todo o histórico dos chamados do recorte.
As duas funcionalidades operam sem chamadas ao Ollama; a comparação textual não substitui uma busca semântica.

## Novidades da V4

- Anexos por chamado: enviar, baixar e remover PNG, JPG/JPEG, WebP, PDF, TXT, LOG e CSV.
- Limite de 10 MB por arquivo e 20 anexos por chamado. Arquivos vazios e formatos incompatíveis são recusados.
- Arquivos armazenados em `uploads/`, com nomes internos aleatórios; nome original preservado no download.
- Histórico registra inclusão e remoção dos anexos. Os anexos não são interpretados pela IA nesta versão.
- Em chamados resolvidos, cada resposta aprovada oferece **Transformar solução em artigo**.
- A ação cria um rascunho persistente, vinculado ao chamado e à resposta, sem duplicar o artigo ao clicar novamente.
- O editor permite salvar como **Rascunho** ou **Publicado**. Somente artigos publicados entram na busca da IA.

Para aproveitar uma solução: aprove uma resposta, confirme que resolveu o problema, marque o chamado como resolvido
e use o botão na resposta do histórico. Revise o título, os passos e as condições de aplicação; remova dados pessoais
antes de publicar. O rascunho inicial usa a resposta editada e aprovada pelo atendente, sem nova chamada à IA.
Fechar o editor mantém o rascunho inicial na biblioteca; alterações no formulário precisam ser salvas.

Os downloads são entregues como arquivo, sem execução ou visualização embutida. A checagem de formato é básica,
não substitui antivírus. Para backup, pare o servidor e copie **`central.db` e a pasta `uploads/`** juntos.
Se definir `UPLOAD_DIR`, inclua esse diretório no backup. Restaurar somente o banco não restaura os arquivos.

## Novidades da V3

- Identidade Órbita: logo vetorial local, navegação em azul escuro e componentes em violeta, com versão móvel.
- Biblioteca com seis guias iniciais: login, VPN, lentidão, aplicativos, impressão e prioridade/SLA.
- Artigos completos, editáveis, com categoria, etiquetas e data de atualização; busca ignora acentos.
- Artigos e etiquetas entram na recuperação de fontes da IA local.
- Atalhos para fila sem responsável e SLA atrasado; ordenação por prazo ou prioridade e limpeza de filtros.

Os guias são referências genéricas de triagem e precisam ser adaptados aos procedimentos da organização.
A migração adiciona os artigos uma única vez, preserva documentos existentes e não recria artigos excluídos.

## Novidades da V2

- Comentários com nome do autor, data e histórico permanente em cada chamado.
- Atribuição de responsável por nome, filtro por atendente e fila de chamados não atribuídos.
- Prioridade editável pelo atendente, independente da sugestão da IA.
- SLA de resolução em horas corridas: Baixa 72h, Média 24h, Alta 8h, Crítica 2h.
- Alertas visuais de atraso e vencimento próximo (últimos 20% do prazo, limitados a 2h).
- Filtros de prazo e atualização da fila a cada minuto enquanto a página está aberta.

O SLA começa na abertura. Alterar prioridade recalcula o prazo desde a abertura; aguardar usuário não pausa a contagem.
Resolver registra o horário e congela o resultado do SLA. Reabrir retoma o prazo original.
Chamados já resolvidos na V1 usam o último evento de resolução disponível; sem evento, a data de abertura é usada como aproximação.
Alterações de responsável e prioridade ficam no histórico. A migração do banco é automática e preserva os dados existentes.
Os alertas aparecem dentro da central; não são enviados por e-mail ou notificação do sistema.
Na V6, o autor dos comentários vem da sessão autenticada. O campo de responsável continua sendo preenchido por nome.

## Executar no Windows

Requer Python 3.10 ou superior.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Abra http://127.0.0.1:8000. A documentação da API fica em http://127.0.0.1:8000/docs.
Os dados são gravados em `central.db`, criado automaticamente na primeira execução.

## IA local

Instale [Ollama](https://ollama.com/download) e execute:

```powershell
ollama pull qwen2.5:3b
ollama serve
```

Se o aplicativo Ollama já estiver ativo, não é necessário executar `ollama serve` novamente.
O download inicial precisa de internet e espaço em disco. A inferência usa os recursos do seu computador,
sem cobrança de API. O tempo de resposta depende do hardware.
O backend usa exclusivamente `http://127.0.0.1:11434`, sem fallback para nuvem.
Para outro modelo local, instale-o e configure antes de iniciar o backend:

```powershell
$env:OLLAMA_MODEL = 'qwen2.5:7b'
```

Se a primeira análise demorar no seu hardware, o tempo limite padrão é de 180 segundos.
Para aumentá-lo, defina antes de iniciar o backend:

```powershell
$env:OLLAMA_TIMEOUT = '300'
```

As mensagens de erro distinguem serviço desconectado, modelo ausente, tempo limite e saída inválida.
Falhas detalhadas ficam no log do backend, sem incluir o conteúdo do chamado.

Referência: [API oficial do Ollama](https://github.com/ollama/ollama/blob/main/docs/api.md).

## Fluxo de uso

1. Em **Base de conhecimento**, cadastre procedimentos reais em texto.
2. Crie um chamado com descrição e impacto do problema.
3. Abra o chamado e clique em **Analisar com IA local**.
4. Confira os trechos recuperados, a prioridade e a justificativa. Edite a resposta e a classificação.
5. Aprove para registrar a resposta ou rejeite a sugestão. Atualize o status durante o atendimento.

A classificação sugerida só altera o chamado após aprovação. O histórico preserva a resposta editada.
Não há envio automático de mensagens ou e-mail. Uma nova análise exige uma nova revisão.
Sem Ollama, chamados e documentos continuam funcionando; a análise informa indisponibilidade.

## Validação

```powershell
python -m unittest discover -s tests -v
node --check frontend/app.js
```

Verificação opcional da interface em Edge, com banco temporário isolado:

```powershell
python -m pip install playwright
python tests/browser_check.py
```

Esse fluxo verifica atribuição, prioridade, comentário, resolução, filtros e navegação com viewport móvel.

Os testes usam banco temporário e simulam o Ollama: aprovação, rejeição, fontes, validação,
indisponibilidade e respostas inválidas do modelo. A qualidade real das sugestões depende do modelo e da documentação.

## Limites da versão atual

- Autenticação local por contas e papéis; sem SSO, MFA ou recuperação por e-mail. Mantenha o servidor em `127.0.0.1`.
- Busca lexical com normalização de acentos e divisão em trechos; não usa embeddings nem busca semântica.
- Documentos cadastrados em texto; extração de conteúdo de PDFs e integrações de e-mail ficam para versões futuras.
- A IA pode errar; fontes recuperadas não garantem que todas as afirmações da resposta estejam fundamentadas.
- Faça backup de `central.db` e `uploads/` com o servidor parado. Não cadastre senhas.
