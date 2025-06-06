# 🚀 Deploy no Streamlit Cloud

## 📋 Pré-requisitos

1. **Conta no GitHub** 
2. **Conta no Streamlit Cloud** (gratuita)
3. **Repositório público** no GitHub

## 🎯 Passo a passo

### 1️⃣ Criar repositório no GitHub

```bash
# Inicializar git (se ainda não estiver)
git init

# Adicionar todos os arquivos
git add .

# Fazer commit inicial
git commit -m "🎉 Primeira versão do Gerador SSIM"

# Conectar com repositório remoto
git remote add origin https://github.com/SEU-USUARIO/gerador-ssim-anac.git

# Fazer push
git push -u origin main
```

### 2️⃣ Configurar Streamlit Cloud

1. Acesse [share.streamlit.io](https://share.streamlit.io)
2. Faça login com sua conta GitHub
3. Clique em **"New app"**
4. Preencha:
   - **Repository**: `SEU-USUARIO/gerador-ssim-anac`
   - **Branch**: `main`
   - **Main file path**: `gerador_ssim_streamlit.py`
   - **App URL**: `gerador-ssim-anac` (ou o nome que desejar)

### 3️⃣ Deploy automático

✅ O Streamlit Cloud irá:
- Detectar automaticamente o `requirements.txt`
- Instalar as dependências
- Fazer deploy da aplicação
- Fornecer uma URL pública

### 4️⃣ URL final

Sua aplicação estará disponível em:
```
https://gerador-ssim-anac.streamlit.app
```

## 🔧 Configurações opcionais

### Secrets (se necessário)
Se precisar de variáveis de ambiente:

1. No painel do Streamlit Cloud
2. Vá em **Settings** → **Secrets**
3. Adicione suas variáveis no formato:
```toml
[general]
API_KEY = "sua-chave-aqui"
```

### Custom Domain
Para domínio personalizado, configure nas configurações do app.

## 🚀 Atualizações

Para atualizar a aplicação:

```bash
# Fazer alterações no código
git add .
git commit -m "✨ Nova funcionalidade"
git push

# O deploy é automático!
```

## 📊 Monitoramento

- **Logs**: Visíveis no painel do Streamlit Cloud
- **Métricas**: Analytics básicas disponíveis
- **Status**: Indicador de health do app

## 🔗 Links úteis

- [Streamlit Cloud](https://share.streamlit.io)
- [Documentação oficial](https://docs.streamlit.io/streamlit-cloud)
- [Troubleshooting](https://docs.streamlit.io/streamlit-cloud/troubleshooting)

---

🎉 **Pronto! Seu gerador SSIM estará online e acessível para qualquer pessoa!** 