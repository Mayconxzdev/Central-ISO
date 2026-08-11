# Workflows n8n

Os quatro JSONs deste diretório são exports sanitizados e não contêm credenciais.

- `01_atualizar_e_analisar.json` — dispara varredura incremental e pipeline de regras;
- `02_consultas_e_relatorios.json` — consulta a API documental;
- `03_alertas_e_acompanhamento.json` — coleta prioridades para acompanhamento;
- `04_erros_e_recuperacao.json` — fluxo de tratamento/recuperação.

No Docker Compose, a API é acessível pelo hostname interno `central-iso-api:8877`.

> Importe os workflows somente em uma instância de teste/demo. Credenciais e destinos reais devem ser configurados fora do JSON versionado.
