# -*- coding: utf-8 -*-
import streamlit as st
import requests
import pandas as pd
import json
import os
from io import StringIO
import re
from datetime import datetime
import tempfile
import urllib3

# Configurar warnings SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Configuração da página ---
st.set_page_config(
    page_title="Gerador SSIM - ANAC API",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Funções auxiliares ---
@st.cache_data(ttl=3600)  # Cache por 1 hora
def carregar_dados_airlines():
    """Carrega dados das companhias aéreas do arquivo CSV"""
    try:
        df_airlines = pd.read_csv('iata_airlines.csv')
        return df_airlines
    except FileNotFoundError:
        st.warning("⚠️ Arquivo 'iata_airlines.csv' não encontrado. Nomes das companhias podem não ser exibidos.")
        return None

@st.cache_data(ttl=1800)  # Cache por 30 minutos
def extrair_dados_api(temporada):
    """Extrai dados da API da ANAC para uma temporada específica"""
    url_base = "https://sas.anac.gov.br/sas/siros_api/ssimfile"
    
    with st.spinner(f'🔄 Consultando API da ANAC para temporada {temporada}...'):
        try:
            response_api = requests.get(
                url_base,
                params={'ds_temporada': temporada},
                verify=False,
                timeout=300
            )
            response_api.raise_for_status()
            
            # Parse do JSON (tratamento para double-escaped JSON)
            response_text = response_api.text
            
            try:
                primeira_decodificacao = json.loads(response_text)
                if isinstance(primeira_decodificacao, str):
                    lista_de_linhas_json = json.loads(primeira_decodificacao)
                else:
                    lista_de_linhas_json = primeira_decodificacao
            except json.JSONDecodeError:
                st.error("❌ Erro ao fazer parse do JSON da API")
                return None
            
            return lista_de_linhas_json
            
        except requests.exceptions.Timeout:
            st.error("❌ Timeout na consulta à API. Tente novamente.")
            return None
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Erro na consulta à API: {e}")
            return None

def extrair_companhias_do_ssim(dados_json):
    """Extrai lista única de companhias aéreas dos dados SSIM"""
    companhias = set()
    
    for item in dados_json:
        if isinstance(item, dict) and 'ssimfile' in item:
            linha = item['ssimfile']
            if linha and linha.startswith('3 ') and len(linha) > 5:
                # Extrai o código da companhia (posições 2-3 na linha)
                codigo_cia = linha[2:4].strip()
                if codigo_cia and codigo_cia.replace(' ', '').isalnum():
                    companhias.add(codigo_cia)
    
    return sorted(list(companhias))

def filtrar_dados_por_companhia(dados_json, codigo_companhia):
    """Filtra dados SSIM por código da companhia aérea"""
    linhas_filtradas = []
    linhas_header = []
    
    # Separar headers e linhas de dados
    for item in dados_json:
        if isinstance(item, dict) and 'ssimfile' in item:
            linha = item['ssimfile']
            if linha:
                # Headers (linhas que começam com 1, 2, ou são zeros)
                if linha.startswith(('1', '2', '0')):
                    linhas_header.append(linha)
                # Dados de voos (linhas que começam com 3)
                elif linha.startswith('3 ') and len(linha) > 5:
                    codigo_linha = linha[2:4].strip()
                    if codigo_linha == codigo_companhia:
                        linhas_filtradas.append(linha)
    
    # Montar resultado: headers + dados filtrados
    resultado = linhas_header + linhas_filtradas
    return resultado

def gerar_nome_arquivo(codigo_companhia, temporada):
    """Gera nome do arquivo baseado na companhia e temporada"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"ssim_{codigo_companhia}_{temporada}_{timestamp}.ssim"

# --- Interface Streamlit ---
def main():
    st.title("✈️ Gerador de Arquivos SSIM")
    st.markdown("### Extrair dados de malha aérea da API da ANAC")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        # Input da temporada
        temporada = st.text_input(
            "🗓️ Temporada (ex: W25, S25)",
            value="W25",
            help="Digite a temporada desejada (formato: W25 para Winter 2025, S25 para Summer 2025)"
        )
        
        # Botão para carregar dados
        if st.button("🔄 Carregar Dados da API", type="primary"):
            if temporada:
                # Limpar cache se necessário
                if st.session_state.get('temporada_atual') != temporada:
                    st.cache_data.clear()
                
                st.session_state['dados_api'] = extrair_dados_api(temporada)
                st.session_state['temporada_atual'] = temporada
                if st.session_state['dados_api']:
                    st.session_state['companhias_disponveis'] = extrair_companhias_do_ssim(st.session_state['dados_api'])
                    st.success(f"✅ Dados carregados! {len(st.session_state['dados_api'])} registros encontrados")
            else:
                st.error("❌ Digite uma temporada válida")
        
        # Informações adicionais
        st.markdown("---")
        st.markdown("### ℹ️ Sobre")
        st.markdown("""
        **Fonte dos dados:** API SIROS - ANAC  
        **Formato:** SSIM (IATA Standard)  
        **Atualização:** Dados em tempo real  
        
        [📖 Documentação SSIM](https://www.iata.org/en/publications/manuals/ssim/)
        """)
    
    # Área principal
    if 'dados_api' in st.session_state and st.session_state['dados_api']:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.success(f"📊 **Dados carregados para temporada:** {st.session_state.get('temporada_atual', 'N/A')}")
            st.info(f"📈 **Total de registros:** {len(st.session_state['dados_api'])}")
            
            # Seleção da companhia
            if 'companhias_disponveis' in st.session_state:
                st.subheader("🏢 Selecionar Companhia Aérea")
                
                companhias = st.session_state['companhias_disponveis']
                
                # Criar lista com nome da companhia (se disponível no CSV)
                df_airlines = carregar_dados_airlines()
                opcoes_companhias = []
                
                for codigo in companhias:
                    nome_cia = "Nome não encontrado"
                    if df_airlines is not None:
                        resultado = df_airlines[df_airlines['IATA Designator'] == codigo]
                        if not resultado.empty:
                            nome_cia = resultado.iloc[0]['Airline Name']
                    opcoes_companhias.append(f"{codigo} - {nome_cia}")
                
                companhia_selecionada = st.selectbox(
                    "Escolha a companhia aérea:",
                    options=range(len(opcoes_companhias)),
                    format_func=lambda x: opcoes_companhias[x],
                    help="Selecione a companhia aérea para filtrar os dados"
                )
                
                if companhia_selecionada is not None:
                    codigo_selecionado = companhias[companhia_selecionada]
                    
                    # Filtrar dados
                    dados_filtrados = filtrar_dados_por_companhia(
                        st.session_state['dados_api'], 
                        codigo_selecionado
                    )
                    
                    st.success(f"✅ **Dados filtrados para {opcoes_companhias[companhia_selecionada]}**")
                    st.info(f"📊 **Linhas encontradas:** {len(dados_filtrados)}")
                    
                    # Preview dos dados
                    if dados_filtrados:
                        with st.expander("👀 Preview dos dados (primeiras 10 linhas)"):
                            for i, linha in enumerate(dados_filtrados[:10]):
                                st.code(linha, language="text")
                    
                    # Botão de download
                    if dados_filtrados:
                        conteudo_ssim = "\n".join(dados_filtrados)
                        nome_arquivo = gerar_nome_arquivo(codigo_selecionado, st.session_state.get('temporada_atual', 'UNK'))
                        
                        st.download_button(
                            label="📥 Baixar arquivo SSIM",
                            data=conteudo_ssim.encode('latin-1'),
                            file_name=nome_arquivo,
                            mime="text/plain",
                            help=f"Baixar arquivo SSIM filtrado para {opcoes_companhias[companhia_selecionada]}"
                        )
        
        with col2:
            st.subheader("📋 Companhias Disponíveis")
            if 'companhias_disponveis' in st.session_state:
                df_companhias = pd.DataFrame({
                    'Código': st.session_state['companhias_disponveis']
                })
                
                # Adicionar nomes das companhias
                df_airlines = carregar_dados_airlines()
                if df_airlines is not None:
                    nomes = []
                    for codigo in st.session_state['companhias_disponveis']:
                        resultado = df_airlines[df_airlines['IATA Designator'] == codigo]
                        if not resultado.empty:
                            nomes.append(resultado.iloc[0]['Airline Name'])
                        else:
                            nomes.append("Nome não encontrado")
                    df_companhias['Nome'] = nomes
                
                st.dataframe(df_companhias, use_container_width=True, height=400)
    
    else:
        st.info("👈 Use o painel lateral para carregar os dados da API")
        
        # Informações sobre o sistema
        st.markdown("""
        ## 📖 Como usar:
        
        1. **Digite a temporada** no campo lateral (ex: W25, S25)
        2. **Clique em "Carregar Dados"** para consultar a API da ANAC
        3. **Selecione a companhia aérea** desejada na lista
        4. **Faça o download** do arquivo SSIM personalizado
        
        ## ℹ️ Sobre os dados:
        
        - **Fonte:** API SIROS da ANAC
        - **Formato:** SSIM (Standard Schedules Information Manual)
        - **Encoding:** Latin-1 (padrão para arquivos SSIM)
        - **Conteúdo:** Malha aérea completa filtrada por companhia
        
        ## 🔗 Links úteis:
        
        - [API ANAC](https://sas.anac.gov.br/sas/siros_api/ssimfile)
        - [Formato SSIM](https://www.iata.org/en/publications/manuals/ssim/)
        """)

if __name__ == "__main__":
    main() 