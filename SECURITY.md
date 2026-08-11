# Segurança e privacidade

## Escopo da versão pública

Este repositório é uma versão de portfólio/demo. Não contém dados corporativos reais, credenciais reais, endereços IP internos ou conexão configurada com infraestrutura empresarial.

## Controles implementados

- fonte documental montada como somente leitura (`:ro`) no Docker Compose;
- variáveis sensíveis via ambiente;
- `.env` fora do versionamento;
- hashing SHA-256 para integridade/idempotência;
- bloqueio de path traversal em endpoints que retornam evidências;
- dados sintéticos no diretório `demo_iso/`;
- IA e parsing externo desabilitados por padrão;
- decisões sensíveis exigem confirmação humana.

## Fora do escopo

O piloto público não implementa SSO/RBAC corporativo. Uma implantação real exigiria autenticação, autorização por perfil, TLS/reverse proxy, gestão centralizada de segredos, observabilidade e políticas formais de retenção/backup.

## Regra de publicação

Nunca publique no repositório:

- `.env` real;
- IP, hostname ou caminho SMB corporativo;
- dumps de banco;
- documentos reais do SGQ;
- nomes/dados pessoais reais;
- tokens, cookies, chaves ou credenciais n8n.
