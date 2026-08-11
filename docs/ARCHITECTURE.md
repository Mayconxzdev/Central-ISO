# Arquitetura

## Componentes

### Scanner e inventário

O scanner percorre a fonte documental, calcula SHA-256, registra metadados e extrai texto dos formatos suportados. Falhas de um arquivo são isoladas para não interromper a varredura completa.

### Extração estruturada

Extratores especializados tentam identificar certificados e não conformidades a partir de nome, caminho e conteúdo extraído.

### Rules Engine

A camada de regras calcula estados como vencimento, proximidade de validade, ausência de eficácia e outras situações que precisam de confirmação.

### Persistência

O projeto suporta SQLite para demo local e PostgreSQL no Compose. O modelo inclui documentos, certificados, NCs, pendências, notas humanas, execuções de scanner, papéis e eventos de automação.

### API

FastAPI expõe health, dashboard, documentos, busca, evidências, inventário, relatórios e ações de varredura/automação.

### n8n

n8n atua como orquestrador/scheduler e consome a API por HTTP. A lógica de domínio permanece no backend Python, facilitando testes e evitando que regras críticas fiquem espalhadas apenas em nós low-code.

### Tauri

O wrapper Tauri fornece uma superfície desktop Windows para a aplicação web local.

## Princípios

- read-only na fonte documental;
- processamento local por padrão;
- idempotência;
- isolamento de falhas;
- evidência antes de decisão;
- humano no circuito;
- demo pública sem dados corporativos.
