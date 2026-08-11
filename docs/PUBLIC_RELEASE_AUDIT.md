# Auditoria da versão pública

Data da auditoria: 2026-08-11

## Escopo

A versão pública foi reconstruída a partir do piloto técnico, preservando o código e as evidências úteis para portfólio e removendo artefatos locais/compilados que não pertencem ao controle de versão.

## Validações executadas

- `python -m pytest -q` em instalação limpa da CI → **32 passed**;
- `python -m compileall -q app scripts` → aprovado;
- busca textual por IPs privados → nenhum encontrado na base publicável;
- busca por nomes corporativos no código/texto → nenhum encontrado na base publicável;
- busca por padrões comuns de GitHub/OpenAI/AWS/Bearer tokens → nenhum encontrado;
- `__pycache__`, `.pytest_cache`, bancos locais e binários removidos;
- `desktop/src-tauri/target/` removido do pacote público e coberto por `.gitignore`;
- workflows n8n revisados sem credenciais embutidas;
- `docker compose config --quiet` → aprovado na CI;
- smoke test da API `/api/v1/health` → aprovado na CI.

## Delimitação de evidência

O repositório mantém propositalmente a classificação de **piloto técnico / proof of concept**. A presença de PostgreSQL, Tauri, n8n ou componentes previstos não deve ser interpretada como evidência de implantação corporativa em produção.

A busca documental pública é determinística e `AI_MODE=disabled`; este case não é utilizado como evidência de RAG ou IA generativa executada.
