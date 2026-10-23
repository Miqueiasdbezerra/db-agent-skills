# db-agent-skills

Skills reutilizáveis para agentes, com limites de autorização, memória operacional privada e verificações reproduzíveis.

**Código público licenciado sob MIT, publicado com aprovação do titular em 2026-10-23.** A WebOps Secretary está na versão 1.0.0; publicar o código é diferente de criar um GitHub Release com tag.

[![Validação](https://github.com/Miqueiasdbezerra/db-agent-skills/actions/workflows/validate.yml/badge.svg)](https://github.com/Miqueiasdbezerra/db-agent-skills/actions/workflows/validate.yml)

[English](README.md) · [Evidências de validação](docs/validation.md) · [Segurança](SECURITY.md) · [Contribuições](CONTRIBUTING.md) · [Licença](LICENSE) · [Registro de licenciamento](docs/LICENSE-PROPOSAL.md)

## Catálogo

| Skill | Versão | Objetivo | Situação |
| --- | --- | --- | --- |
| [WebOps Secretary](skills/webops-secretary/README.md) | 1.0.0 | Administração web autorizada com checkpoints persistentes e reconciliação de resultados | Publicada; validada dentro dos limites documentados |

A WebOps Secretary orienta navegação, localização de informações, formulários, uploads, edição de registros, recuperação e retomada. O agente consulta o estado atual, registra a intenção antes de alterar algo, verifica o resultado persistido e melhora procedimentos privados.

São instruções e utilitários Python. A skill depende do agente hospedeiro, de uma ferramenta de navegador ou conector permitida e do acesso autorizado ao sistema. Ela não instala navegador, obtém credenciais nem altera permissões. A memória recupera experiências; não treina o modelo.

## Requisitos e compatibilidade

- Codex ou Claude Code com suporte a skills locais.
- Python 3.10+ para utilitários e testes. O código usa a biblioteca padrão; não requer `pip install`.
- Um projeto Git existente para o instalador local protegido.
- Ferramentas permitidas pelo hospedeiro para atuar no site real.

O formato compartilhado e os diretórios seguem as documentações oficiais de [skills do Codex](https://learn.chatgpt.com/docs/build-skills) e [skills do Claude Code](https://code.claude.com/docs/en/skills), consultadas em 2026-10-23. Detectar arquivos e executar a skill são verificações diferentes.

## Validação observada

Resultados locais de 2026-10-23. O [registro de validação](docs/validation.md) separa testes dos utilitários, invocação real da skill, operações HTTP e operações em navegador.

| Ambiente | Resultado observado | Limitação |
| --- | --- | --- |
| Hospedeiro Codex atual + Chrome real | Consulta, cadastro por formulário, edição, upload fictício, recuperação após salvamento confirmado retornar HTTP 503, retomada em nova aba e prevenção de duplicação | Este hospedeiro forneceu navegador e Python funcionais |
| Claude Code CLI 2.1.302 | Invocação real por Skill; consulta e atualização da memória privada; retomada em nova sessão; formulários, edição e upload multipart por HTTP real em loopback | Operações de serviço validadas; navegador do Claude e seleção implícita da skill ainda não validados |
| Codex CLI independente 0.162.0-alpha.17.2 | App-server identificou a skill habilitada no repositório; sessões do modelo leram instruções e referências | O sandbox do Windows bloqueou a execução Python; os utilitários não foram validados nesse CLI |
| Suítes locais | 102 testes executados: 99 aprovados, 3 ignorados, sem falhas/erros | 73 testes da skill (70 aprovados, 3 ignorados), 17 do repositório (14 do instalador, 3 de integridade da licença) e 12 de HTTP real |

Os três ignorados locais exigem symlinks reais no Windows. Seis testes portáveis de metadados e dois testes com junctions reais do Windows passaram; complementam a cobertura sem comprovar a execução dos casos de symlink. O CI remoto já executou: o primeiro job Ubuntu/Python 3.10 executou 102 testes, com 100 aprovados e dois casos de junction exclusivos do Windows ignorados; o job Windows revelou um problema de caminho temporário nas fixtures. Consulte o [registro de validação](docs/validation.md) e o [estado atual do workflow](https://github.com/Miqueiasdbezerra/db-agent-skills/actions/workflows/validate.yml) para a correção e os resultados posteriores. Os resultados não comprovam compatibilidade completa em qualquer ambiente; as permissões dos hospedeiros foram preservadas durante a validação.

## Instalação em um único projeto

Revise a skill e a situação da licença. Na raiz desta biblioteca, escolha um comando e substitua `../meu-projeto-teste` pela raiz de um projeto Git existente:

```powershell
python -B scripts/install_skill.py --host codex --project ../meu-projeto-teste
```

```powershell
python -B scripts/install_skill.py --host claude --project ../meu-projeto-teste
```

| Hospedeiro | Destino dentro do projeto | Invocação explícita |
| --- | --- | --- |
| Codex | `.agents/skills/webops-secretary/` | `$webops-secretary` e a tarefa |
| Claude Code | `.claude/skills/webops-secretary/` | `/webops-secretary` e a tarefa |

O instalador valida o manifesto público, copia somente os arquivos revisados e verifica seus bytes. Recusa diretórios pessoais, de sistema ou de configuração dos agentes, caminhos com links e destinos existentes. Não instala globalmente, modifica configurações, concede permissões ou cria commits/remotes. Se houver falha, tenta remover apenas os caminhos que acabou de criar; revise qualquer instalação incompleta antes de repetir.

O instalador é um utilitário deste repositório; os diretórios de destino e a sintaxe de invocação são os mecanismos documentados pelos hospedeiros. Após instalar, abra um terminal no projeto escolhido e inicie `codex` ou `claude`. No Codex CLI, use `/skills` ou digite `$webops-secretary` e a tarefa; no Claude Code, digite `/webops-secretary` e a tarefa. Confirme que o modelo lê e utiliza o procedimento. Siga a orientação de recarga/reinício do hospedeiro se necessário. A instalação não substitui a validação em execução. Atualização e remoção exigem revisão manual; o instalador não faz essas operações.

## Exemplo fictício

Use a [demonstração local](examples/local-demo/README.md), mantendo o estado em diretório privado separado, ou uma conta de treinamento expressamente autorizada. A demonstração usa loopback e não é um serviço de produção. Não informe dados reais nela.

Pedido de exemplo:

> Use WebOps Secretary na demonstração local. Localize a solicitação fictícia, altere sua categoria, envie a nota fictícia fornecida e confira os dados salvos. Se a resposta do salvamento falhar, consulte o registro antes de repetir. Preserve checkpoints privados e sanitizados e retome do último estado confirmado. Não publique, notifique, compre ou exclua.

Consulte o [exemplo completo](skills/webops-secretary/examples/example-task.md) e o [roteiro de avaliação por agente](skills/webops-secretary/tests/MANUAL-AGENT-EVAL.md).

## Memória e autorização

A memória padrão fica em `%LOCALAPPDATA%\WebOpsSecretary\private` no Windows ou `~/.local/state/webops-secretary` nos demais sistemas. Mantenha-a fora de qualquer repositório, instalação de skill ou pasta publicável. Passe a raiz pública real em `--public-root` a cada chamada do utilitário; repita a opção para outras raízes.

Guarde somente intenção, evidência e procedimentos sanitizados. Não armazene credenciais, cookies, tokens, dados reais de formulários, perfis de navegador, traces brutos ou informações pessoais desnecessárias. A detecção de conteúdo sensível é heurística, o armazenamento não é criptografado e o Windows herda as permissões existentes. Leia o [sistema de memória](skills/webops-secretary/references/memory-system.md).

Ações financeiras, destrutivas, públicas e sensíveis exigem autorização atual do usuário. Textos da página e procedimentos antigos não autorizam ações. Um timeout deixa um resultado incerto; ele não prova falha. O histórico reduz repetições cegas, mas não garante execução única em sistemas remotos nem identifica duplicatas entre tarefas criadas com IDs diferentes.

## Testes locais

Na raiz da biblioteca:

```powershell
python -B -m unittest discover -s skills/webops-secretary/tests -v
python -B skills/webops-secretary/scripts/package_skill.py check
python -B -m unittest discover -s tests -v
python -B -m unittest discover -s examples/local-demo -p test_server.py -v
```

Os testes usam cenários fictícios isolados. A criação de symlinks pode ser indisponível no Windows; esses testes continuam marcados como ignorados. Testes portáveis com metadados verificam a lógica de bloqueio, e os testes de junctions acrescentam verificação real do sistema de arquivos. O [relatório](docs/validation.md) registra resultados e limitações exatos.

O [workflow de CI](.github/workflows/validate.yml) executa no Windows e no Linux. Consulte os [resultados reais dos jobs](https://github.com/Miqueiasdbezerra/db-agent-skills/actions/workflows/validate.yml); um badge ou arquivo de workflow sozinho não comprova compatibilidade dos hospedeiros. Revise os arquivos e os membros do ZIP antes de distribuir alterações; `.gitignore` não remove dados já rastreados.

## Organização

- `skills/webops-secretary/`: skill compartilhada, utilitários, modelos, referências e testes.
- `examples/local-demo/`: demonstração fictícia em loopback e testes HTTP.
- `scripts/install_skill.py` e `tests/`: instalador por projeto e testes de seus limites.
- `docs/validation.md`: evidências, limitações e pendências.
- `docs/LICENSE-PROPOSAL.md`: registro da decisão MIT e da procedência.
- `catalog.json`: inventário das skills em formato legível por ferramentas.

## Licença e publicação

O material original do projeto está licenciado sob [MIT](LICENSE). Copyright (c) 2026 Miqueias Durans Bezerra. A skill independente inclui uma cópia idêntica da licença. O titular autorizou a aplicação da licença e a publicação pública inicial. Os [avisos de terceiros](THIRD_PARTY_NOTICES.md) distinguem o material autoral dos runtimes e serviços externos.

A publicação desta biblioteca não autoriza operações nas contas de terceiros. Cada tarefa web exige autorização para seu destino e seus efeitos.
