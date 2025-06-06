# ✈️ Gerador SSIM - API ANAC

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://gerador-ssim-anac.streamlit.app)

Aplicativo web para extrair e filtrar dados de malha aérea da API SIROS da ANAC, gerando arquivos SSIM personalizados por companhia aérea e temporada.

## 🚀 Acesso Online

**🔗 [Acesse o aplicativo aqui](https://gerador-ssim-anac.streamlit.app)**

## 🎯 Funcionalidades

- ✅ **Consulta direta à API da ANAC** para dados atualizados
- ✅ **Filtragem por companhia aérea** (códigos IATA/ICAO)
- ✅ **Seleção de temporada** (W25, S25, etc.)
- ✅ **Download de arquivos SSIM** no formato padrão
- ✅ **Interface amigável** com preview dos dados
- ✅ **Identificação automática** de companhias disponíveis

## 📖 Como usar

### 1️⃣ Carregar dados
- Digite a **temporada** desejada (ex: `W25`, `S25`)
- Clique em **"Carregar Dados da API"**
- Aguarde o carregamento

### 2️⃣ Selecionar companhia
- Escolha a **companhia aérea** na lista
- Visualize o **preview dos dados** filtrados

### 3️⃣ Download
- Clique em **"Baixar arquivo SSIM"**
- Arquivo salvo com nome único contendo código, temporada e timestamp

## 📊 Dados Suportados

### Companhias Brasileiras Disponíveis
- **G3** - GOL Linhas Aéreas
- **AD** - Azul Brazilian Airlines  
- **LA** - LATAM Airlines
- **JJ** - TAM (histórico)
- E muitas outras...

### Temporadas
- **W25**: Winter 2025 (out/2024 - mar/2025)
- **S25**: Summer 2025 (mar/2025 - out/2025)
- Outras conforme disponibilidade na API

## 🛠️ Tecnologias

- **Python 3.8+**
- **Streamlit** - Interface web
- **Pandas** - Manipulação de dados
- **Requests** - Consulta à API

## 📊 Estrutura SSIM

Arquivos gerados seguem o padrão **SSIM (Standard Schedules Information Manual)**:
