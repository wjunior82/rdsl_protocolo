# Segurança do Projeto

## Visão Geral

Este documento descreve as medidas de segurança implementadas no API de Protocolo (RDSL Protocolo).

## Configuração Inicial

### 1. Configurar Variáveis de Ambiente

1. Copie o arquivo `.env.example` para `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edite o arquivo `.env` e preencha com suas credenciais:
   ```env
   # Credenciais PostgreSQL
   POSTGRES_HOST=seu-host
   POSTGRES_PORT=5432
   POSTGRES_DATABASE=seu-database
   POSTGRES_USER=seu-usuario
   POSTGRES_PASSWORD=sua-senha-segura

   # Credenciais SQL Server
   SQLSERVER_SERVER=seu-sqlserver
   SQLSERVER_DATABASE=seu-database
   SQLSERVER_UID=seu-usuario
   SQLSERVER_PASSWORD=sua-senha-segura

   # API Key (mínimo 20 caracteres recomendado 32+)
   API_KEY=sua-api-key-muito-segura-aqui

   # Origens CORS permitidas (para rede interna)
   ALLOWED_ORIGINS=http://localhost:8000,http://seu-servidor-interno:8000

   # Configuração de ambiente
   ENVIRONMENT=production
   DEBUG=False
   LOG_LEVEL=INFO
   ```

3. **IMPORTANTE**: Nunca commite o arquivo `.env` no Git. Use `.gitignore` para excluir.

### 2. Instalar Dependências

```bash
pip install -r requirements.txt
```

## Recursos de Segurança Implementados

### ✅ Autenticação por API Key

Todos os endpoints requerem uma API Key no header `X-API-Key`:

```bash
curl -H "X-API-Key: sua-api-key" http://localhost:8000/filters
```

**Especificações:**
- Comprimento mínimo: 20 caracteres (recomendado 32+)
- Header: `X-API-Key`
- Estilo: Bearer token style
- Validação: Comparação direta em tempo de execução

### ✅ Validação de Entrada (Input Validation)

Todas as entradas são validadas para:
- **Comprimento máximo**: Proteção contra buffer overflow
- **Caracteres permitidos**: Apenas alfanuméricos, hyphens, underscores, dots
- **Null byte injection**: Removidos automaticamente
- **SQL Injection**: Queries usam parameterized statements (prepared statements)

Funções de validação:
- `validate_protocolo()` - Valida números de protocolo
- `validate_scope()` - Valida nomes de escopo/tabela
- `validate_filter_list()` - Valida listas de filtros

### ✅ Proteção CORS (Cross-Origin Resource Sharing)

- **Origens permitidas**: Configuradas via `ALLOWED_ORIGINS` no `.env`
- Por padrão: Apenas localhost e servidores internos
- Métodos permitidos: `GET`, `POST`
- Headers permitidos: `Content-Type`, `X-API-Key`

### ✅ Trusted Host Middleware

- Valida o header `Host` das requisições
- Previne request-smuggling attacks
- Configurado para aceitar apenas hosts em `ALLOWED_ORIGINS`

### ✅ Credenciais Seguras

- **Antes**: Credenciais hardcoded no código
- **Depois**: Carregadas do `.env` em tempo de execução
- Nunca aparecem em logs ou mensagens de erro
- Gerenciadas via `Settings` class com validação

### ✅ Logging e Auditoria

Sistema de logging com separação de níveis:
- `INFO`: Requisições normais (com ID da API Key parcial)
- `WARNING`: Tentativas de acesso inválido
- `ERROR`: Erros internos

Formato do log:
```
2026-03-12 10:30:45 - INFO - API Request - Endpoint: /diff, APIKey: 1234567890..., Params: {...}
2026-03-12 10:31:20 - ERROR - Security Event - Endpoint: /list, Error: Invalid filter value
```

### ✅ Tratamento de Erros Seguro

- **Erros públicos**: Mensagens genéricas para cliente
- **Erros internos**: Detalhes completos apenas em logs
- Previne información disclosure attacks
- Códigos HTTP apropriados:
  - 400: Bad Request (entrada inválida)
  - 401: Unauthorized (sem API Key)
  - 403: Forbidden (API Key inválida)
  - 500: Internal Server Error (erro interno)

### ✅ SQL Injection Prevention

Implementado via:
1. **Parameterized Queries**: Uso de `%s` placeholders
2. **Prepared Statements**: Via psycopg2 e SQL Server drivers
3. **Query Validation**: Validação de escopo antes de executar
4. **Whitelist de Tabelas**: Apenas tabelas pré-configuradas são acessadas

## Endpoints Seguros

### GET /filters
Retorna filtros disponíveis com validação de API Key.

```bash
curl -H "X-API-Key: sua-chave" http://localhost:8000/filters
```

### GET /list
Lista protocolos com filtros opcionais.

```bash
curl -H "X-API-Key: sua-chave" \
  "http://localhost:8000/list?contrato_regional=SP&contrato_nome_prestador=Hospital%20XYZ"
```

### GET /diff
Compara duas versões de protocolo.

```bash
curl -H "X-API-Key: sua-chave" \
  "http://localhost:8000/diff?scope=report.vw_regras_medicamentos_historico&from=PROTO001&to=PROTO002"
```

### POST /insert-controle-protocolo
Insere novo controle de protocolo.

```bash
curl -X POST -H "X-API-Key: sua-chave" \
  -H "Content-Type: application/json" \
  -d '{"NUM_PROTOCOLO": "PROTO123", "NME_USUARIO": "usuario@example.com"}' \
  http://localhost:8000/insert-controle-protocolo
```

### POST /delete-controle-protocolo
Deleta controle de protocolo.

```bash
curl -X POST -H "X-API-Key: sua-chave" \
  -H "Content-Type: application/json" \
  -d '{"NUM_PROTOCOLO": "PROTO123"}' \
  http://localhost:8000/delete-controle-protocolo
```

## Boas Práticas

### 🔐 Para o Administrador

1. **Gere uma API Key forte**:
   ```python
   import secrets
   api_key = secrets.token_urlsafe(32)  # Gera chave de 32 caracteres
   print(api_key)
   ```

2. **Rotação de Credenciais**: Altere regularmente (recomendado mensalmente)

3. **Monitoramento**: Revise logs regularmente para atividades suspeitas

4. **Backup do .env**: Armazene em sistema seguro (não no Git)

5. **Acesso ao .env**: Restrinja permissões de arquivo:
   ```bash
   chmod 600 .env
   ```

### 🔐 Para o Desenvolvedor

1. **Nunca commite credenciais**:
   ```bash
   # Adicionar ao .gitignore
   .env
   .env.local
   *.pem
   *.key
   ```

2. **Use variáveis de ambiente** para todas as configurações sensíveis

3. **Implemente rate limiting** em produção (considerar próximas versões)

4. **Use HTTPS em produção**:
   ```bash
   # Executar com SSL
   uvicorn app:app --ssl-keyfile=key.pem --ssl-certfile=cert.pem
   ```

5. **Mantenha o logging habilitado** para auditoria

### 🔐 Para o Usuário da API

1. **Guarde sua API Key com segurança**
   - Não compartilhe em emails ou chats
   - Não coloque em código-fonte
   - Use em variáveis de ambiente do cliente

2. **Use HTTPS** ao fazer requisições em produção

3. **Implemente timeout** nas suas requisições

4. **Monitore respostas de erro** para possíveis ataques

## Vulnerabilidades Conhecidas na Versão Anterior

| Vulnerabilidade | Risco | Mitigação Implementada |
|---|---|---|
| Credenciais hardcoded | CRÍTICO | Carregadas do `.env` |
| Sem autenticação | CRÍTICO | API Key obrigatória |
| CORS aberto para `*` | ALTO | Restrito para hosts internos |
| Sem validação de entrada | ALTO | Validação rigorosa em todos inputs |
| Erro detalhado ao usuário | MÉDIO | Mensagens genéricas com detalhes em logs |
| Sem log de auditoria | MÉDIO | Sistema completo de logging implementado |
| SQL injection | MÉDIO | Parameterized queries |

## Checklist de Segurança para Produção

- [ ] `.env` configurado com credenciais reais
- [ ] `.env` adicionado ao `.gitignore`
- [ ] API Key alterada de valor padrão
- [ ] HTTPS ativado em produção
- [ ] `ALLOWED_ORIGINS` configurado para seu domínio
- [ ] `DEBUG` setado para `False`
- [ ] `LOG_LEVEL` setado para `INFO` ou `WARNING`
- [ ] Backup regular do `.env` em local seguro
- [ ] Logs monitorados regularmente
- [ ] Firewall configurado para aceitar apenas requisições autorizadas
- [ ] Credenciais do banco de dados alteradas periodicamente

## Próximos Passos Recomendados

1. **Rate Limiting**: Implementar limite de requisições por API Key
2. **OAuth2**: Para integração com sistemas mais complexos
3. **JWT**: Para melhor segurança em arquitetura distribuída
4. **IP Whitelist**: Restringir por endereço IP
5. **Encryption**: Encriptar dados sensíveis em trânsito e em repouso
6. **WAF (Web Application Firewall)**: Em ambiente de produção
7. **SIEM**: Sistema de detecção de intrusões

## Contato para Segurança

Se encontrar uma vulnerabilidade de segurança, por favor **não** abra uma issue pública. Entre em contato com a equipe de segurança diretamente.

## Referências

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Python dotenv](https://pypi.org/project/python-dotenv/)
- [PEP 8 - Security best practices](https://www.python.org/dev/peps/pep-0008/)

---

**Versão**: 1.0 | **Data**: 2026-03-12 | **Status**: ✅ Implementado
