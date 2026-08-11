# Testes e validação

## Resultado desta versão pública

```text
30 passed, 1 skipped
```

Executado com:

```bash
python -m pytest -q
python -m compileall -q app scripts
```

## Cobertura funcional representada na suíte

- health/dashboard/API;
- paginação e filtros de documentos;
- scanner idempotente;
- política read-only;
- path traversal;
- normalização de extensões;
- extração de certificados e NCs;
- regras de vencimento e eficácia;
- workflow de certificados;
- reconciliação de inventário;
- hashing progressivo, pause/resume;
- arquivos Office protegidos;
- modos demo/production;
- integridade de textos da interface.

## CI

A GitHub Action executa instalação limpa, `compileall`, `pytest` e uma verificação de publicação para IPs privados.
