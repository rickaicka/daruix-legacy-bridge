# Daruix Legacy Bridge

API privada, somente leitura, que executa no **Cron (Debian/Ubuntu)** e consulta o `SGO.accdb` do **Conan** por meio de um compartilhamento Samba montado como somente leitura.

## Fluxo

`Angular/Ionic → Django BFF (VPS) → WireGuard → Legacy Bridge (Cron) → Samba → Access (Conan)`

O front-end nunca chama este serviço diretamente. A porta `8100` deve ser vinculada somente ao IP WireGuard do Cron e liberada no firewall apenas para o IP WireGuard da VPS.

## Endpoints

### Descoberta comercial e de propostas

`GET /v1/commercial/tables` consulta uma lista fechada de tabelas permitidas e
retorna, para cada recurso, o nome real encontrado no Access, quantidade de
linhas, colunas e possíveis nomes semelhantes. Além dos catálogos de clientes,
o levantamento inclui propostas, serviços solicitados, contatos da proposta,
parcelas, planos de pagamento, tipos de proposta, divisões, departamentos,
projetos, obras e usuários.

Este endpoint é somente de metadados. O consumidor nunca envia diretamente um
nome de tabela do Access.

Os recursos de propostas podem ser lidos de forma paginada por
`GET /v1/commercial/{resource}`. São aceitos `offset`, `limit`, `search` e o par
`filter_column`/`filter_value`. Apenas recursos presentes na lista fechada
`PROPOSAL_TABLES` podem devolver linhas. `T_Usuario` nunca é exposta por esse
endpoint porque contém credenciais legadas.

Todos, exceto `/health/live`, exigem `Authorization: Bearer <BRIDGE_SERVICE_TOKEN>` e IP permitido.

- `GET /health/live`
- `GET /health/ready`
- `POST /v1/authenticate`
- `GET /v1/clients?search=&limit=100`
- `GET /v1/clients/catalog`
- `GET /v1/works?client_name=&client_document=&search=&limit=100`
- `GET /v1/works/{id}`
- `GET /v1/commercial/tables`
- `GET /v1/commercial/{resource}`
- `GET /v1/business-segments`
- `GET /v1/company-types`

## Executar os testes

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```

Os testes usam um repositório falso e não precisam do Access.

## Implantar no Cron

1. Monte o compartilhamento do Conan em `/mnt/conan/sgo`, usando uma conta Samba com permissão somente de leitura.
2. Copie `.env.example` para `.env`, gere um token aleatório e ajuste o nome real do `.accdb`.
3. Configure o WireGuard para que o Cron tenha o IP privado `10.70.0.2` e a VPS `10.70.0.1`.
4. Execute `docker compose up -d --build`.
5. Teste a partir da VPS:

```bash
curl -H "Authorization: Bearer $LEGACY_BRIDGE_TOKEN" http://10.70.0.2:8100/health/ready
```

## Variáveis do BFF

```env
LEGACY_BRIDGE_MODE=http
LEGACY_BRIDGE_URL=http://10.70.0.2:8100
LEGACY_BRIDGE_TOKEN=mesmo-token-do-bridge
LEGACY_BRIDGE_CONNECT_TIMEOUT=3
LEGACY_BRIDGE_READ_TIMEOUT=15
```

O cliente HTTP do BFF deve continuar expondo ao Angular os endpoints Django atuais. Este projeto não contém JWT, PostgreSQL, regras de memorando, e-mail ou permissões do Hub.

## Segurança

- O `.accdb` é montado e aberto como somente leitura.
- O token nunca deve ser versionado, colocado em URL ou registrado em log.
- O acesso é protegido por token, allowlist de IP, WireGuard e firewall.
- A comparação de senha em texto puro existe apenas por compatibilidade temporária com o Access legado.
- O `uvicorn` inicia sem access log para evitar registros desnecessários das rotas.
