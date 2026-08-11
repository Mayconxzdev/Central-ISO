# Estudo de caso — Central ISO

## Contexto

O piloto surgiu a partir de necessidades observadas junto à área de Qualidade de uma empresa industrial que trabalha com documentação controlada, certificados de produtos/equipamentos Ex e processos de não conformidade.

O acompanhamento existente dependia fortemente de planilhas, pastas de rede e conferências manuais. Isso tornava mais lento localizar documentos, verificar vencimentos e reunir evidências para auditorias.

## Minha atuação

Atuei sozinho no ciclo completo:

1. conversei com stakeholders e auditores internos para entender o processo real;
2. mapeei o AS-IS e as regras de negócio;
3. identifiquei quais verificações poderiam ser determinísticas;
4. pesquisei uma stack gratuita/open-source;
5. desenvolvi backend, automações, persistência e interface;
6. criei dados sintéticos e testes para validar a hipótese sem publicar informação corporativa;
7. documentei limites, riscos e decisões de segurança.

## Problema → solução

| Antes | Piloto proposto |
|---|---|
| conferência manual de pastas | varredura periódica e sob demanda |
| risco de reprocessar o mesmo arquivo | SHA-256 e processamento idempotente |
| informação dispersa | inventário e dashboard centralizados |
| vencimentos conferidos manualmente | regras determinísticas de prazo |
| NCs acompanhadas por busca manual | extração estruturada + regras de eficácia/prazo |
| dependência de consulta humana contínua | alertas e fila de pendências |
| risco de alteração da fonte | acesso documental read-only |

## Decisões relevantes

### Determinístico antes de generativo

Embora o projeto tenha sido concebido em um contexto de automação e IA, a versão pública mantém `AI_MODE=disabled`. Regras de validade, prazos e estados são calculadas de forma determinística. Isso evita apresentar inferência probabilística como decisão de conformidade.

### Read-only por desenho

O scanner precisa ler documentos oficiais, mas não precisa modificá-los. No Docker, a pasta de origem é montada com `:ro`, reduzindo a superfície de risco de alteração ou exclusão acidental.

### Idempotência

Cada arquivo é identificado por SHA-256. Arquivos sem mudança podem ser preservados entre varreduras e documentos repetidos podem ser detectados sem depender somente do nome.

### Humano continua responsável

O Central ISO sinaliza situações e organiza evidências. Ele não libera produto, encerra NC ou declara conformidade automaticamente.

## Resultado real do piloto

O código funcional provou que regras coletadas em entrevistas com a Qualidade podiam ser convertidas em um pipeline técnico reproduzível, executando localmente e sem licenças SaaS obrigatórias.

O projeto parou como piloto técnico e, por isso, não há métricas de adoção em produção. Essa limitação é mantida explicitamente para não transformar uma prova de conceito em um case de produção inexistente.
