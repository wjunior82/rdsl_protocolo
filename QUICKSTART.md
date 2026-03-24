# Guia Rápido de Instalação e Segurança

## 1️⃣ Instalação Inicial

```bash
# Criar ambiente virtual (opcional)
python -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt
```

## 2️⃣ Configurar Segurança

```bash
# Copiar template de ambiente
cp .env.example .env

# Editar arquivo .env (use seu editor favorito)
# Preencha com suas credenciais reais:
# - POSTGRES_USER, POSTGRES_PASSWORD
# - SQLSERVER_UID, SQLSERVER_PASSWORD
# - API_KEY (gere uma chave segura)
# - ALLOWED_ORIGINS (seus servidores internos)
```

### Gerar API Key Segura

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 3️⃣ Executar a Aplicação

```bash
# Desenvolvimento
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Produção (com HTTPS)
uvicorn app:app --ssl-keyfile=key.pem --ssl-certfile=cert.pem --host 0.0.0.0 --port 443
```

## 4️⃣ Testar API com Segurança

```bash
# Obter API Key do .env
export API_KEY=$(grep "^API_KEY=" .env | cut -d= -f2)

# Testar endpoint /filters
curl -H "X-API-Key: $API_KEY" http://localhost:8000/filters

# Testar endpoint /list
curl -H "X-API-Key: $API_KEY" "http://localhost:8000/list?contrato_regional=SP"

# Testar endpoint /diff
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/diff?scope=report.vw_regras_medicamentos_historico&from=PROTO1&to=PROTO2"
```

## 🔐 Lista de Verificação

- [ ] `.env` criado com credenciais reais
- [ ] `.env` está no `.gitignore`
- [ ] `API_KEY` é forte (32+ caracteres)
- [ ] `ALLOWED_ORIGINS` contém seus servidores
- [ ] Dependências instaladas: `pip install -r requirements.txt`
- [ ] Credenciais do banco testadas
- [ ] Logs estão sendo gerados

## 📖 Documentação Completa

Leia [SECURITY.md](SECURITY.md) para:
- Explicação detalhada de cada medida de segurança
- Boas práticas recomendadas
- Checklist para produção
- Exemplos de uso completos

## ❓ Dúvidas Frequentes

**P: Preciso usar HTTPS?**
R: Sim, em produção. Use certificados SSL/TLS válidos.

**P: Posso deixar ALLOWED_ORIGINS como `*`?**
R: Não recomendado. Configure apenas os domínios que usarão a API.

**P: Com que frequência devo rotacionar a API Key?**
R: Recomendado mensalmente ou após suspeita de comprometimento.

**P: Onde armazeno o .env em produção?**
R: Use secret management (AWS Secrets Manager, Azure Key Vault, etc)

---

Para mais informações, consulte [SECURITY.md](SECURITY.md)
