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

@st.cache_data(ttl=3600)  # Cache por 1 hora
def carregar_dados_airports():
    """Carrega dados dos aeroportos do arquivo CSV"""
    try:
        df_airports = pd.read_csv('airport.csv')
        return df_airports
    except FileNotFoundError:
        st.warning("⚠️ Arquivo 'airport.csv' não encontrado. Conversão de horários não estará disponível.")
        return None

def obter_offset_aeroporto(codigo_aeroporto, df_airports):
    """Obtém o offset UTC de um aeroporto"""
    if df_airports is None:
        return -3  # Default para horário de Brasília
    
    # Buscar por código IATA
    resultado = df_airports[df_airports['IATA'] == codigo_aeroporto]
    if not resultado.empty:
        return resultado.iloc[0]['Timezone']
    
    # Se não encontrar, retorna -3 (Brasília)
    return -3

def converter_horario_ssim(linha_ssim, df_airports, para_brasilia=False):
    """Converte horários de uma linha SSIM para horário de Brasília"""
    if not para_brasilia or not linha_ssim.startswith('3 '):
        return linha_ssim
    
    # Extrair aeroportos da linha SSIM
    # Formato: 3 XX NNNNNNNJDDMMMYYDDMMMYYOOOOOOO  AAAHHMM-TTTT  BBBHHMM-TTTT  ...
    try:
        # Encontrar posições dos aeroportos e horários
        partes = linha_ssim.split()
        
        # Buscar padrões de aeroporto + horário (ex: GRU12001200-0300)
        padrao_aeroporto_horario = re.findall(r'([A-Z]{3})(\d{4})(\d{4})([-+]\d{4})', linha_ssim)
        
        linha_convertida = linha_ssim
        
        for aeroporto, hora_partida, hora_chegada, offset_original in padrao_aeroporto_horario:
            offset_aeroporto = obter_offset_aeroporto(aeroporto, df_airports)
            offset_brasilia = -3  # UTC-3
            
            # Converter offset format (-0300 para -3)
            try:
                offset_atual = int(offset_original[:3])  # -030 -> -3
            except:
                offset_atual = offset_aeroporto
            
            # Calcular diferença de horas para Brasília
            diferenca_horas = offset_brasilia - offset_atual
            
            if diferenca_horas != 0:
                # Converter horário de partida
                try:
                    hora_part_int = int(hora_partida)
                    horas_part = hora_part_int // 100
                    minutos_part = hora_part_int % 100
                    
                    # Aplicar diferença
                    horas_part += diferenca_horas
                    
                    # Ajustar se passou de 24h ou ficou negativo
                    if horas_part >= 24:
                        horas_part -= 24
                    elif horas_part < 0:
                        horas_part += 24
                    
                    hora_partida_nova = f"{horas_part:02d}{minutos_part:02d}"
                    
                    # Converter horário de chegada
                    hora_cheg_int = int(hora_chegada)
                    horas_cheg = hora_cheg_int // 100
                    minutos_cheg = hora_cheg_int % 100
                    
                    # Aplicar diferença
                    horas_cheg += diferenca_horas
                    
                    # Ajustar se passou de 24h ou ficou negativo
                    if horas_cheg >= 24:
                        horas_cheg -= 24
                    elif horas_cheg < 0:
                        horas_cheg += 24
                    
                    hora_chegada_nova = f"{horas_cheg:02d}{minutos_cheg:02d}"
                    
                    # Substituir na linha
                    texto_original = f"{aeroporto}{hora_partida}{hora_chegada}{offset_original}"
                    texto_novo = f"{aeroporto}{hora_partida_nova}{hora_chegada_nova}-0300"
                    linha_convertida = linha_convertida.replace(texto_original, texto_novo)
                    
                except (ValueError, IndexError):
                    # Se der erro na conversão, manter original
                    continue
        
        return linha_convertida
        
    except Exception:
        # Se der qualquer erro, retorna a linha original
        return linha_ssim

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

def filtrar_dados_por_companhia(dados_json, codigo_companhia, converter_para_brasilia=False, df_airports=None):
    """Filtra dados SSIM por código da companhia aérea e opcionalmente converte horários"""
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
                    if codigo_companhia == "TODAS":
                        # Se for "TODAS", incluir todas as linhas de dados
                        linha_processada = converter_horario_ssim(linha, df_airports, converter_para_brasilia)
                        linhas_filtradas.append(linha_processada)
                    else:
                        # Filtrar por companhia específica
                        codigo_linha = linha[2:4].strip()
                        if codigo_linha == codigo_companhia:
                            linha_processada = converter_horario_ssim(linha, df_airports, converter_para_brasilia)
                            linhas_filtradas.append(linha_processada)
    
    # Montar resultado: headers + dados filtrados
    resultado = linhas_header + linhas_filtradas
    return resultado

def gerar_nome_arquivo(codigo_companhia, temporada, horario_brasilia=False):
    """Gera nome do arquivo baseado na companhia e temporada"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sufixo_horario = "_HORARIO_BRASILIA" if horario_brasilia else "_HORARIO_LOCAL"
    
    if codigo_companhia == "TODAS":
        return f"ssim_TODAS_COMPANHIAS_{temporada}{sufixo_horario}_{timestamp}.ssim"
    else:
        return f"ssim_{codigo_companhia}_{temporada}{sufixo_horario}_{timestamp}.ssim"

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
        
        # Opção de conversão de horário
        st.markdown("---")
        st.markdown("### 🕐 Configuração de Horários")
        
        converter_horarios = st.radio(
            "Formato dos horários:",
            options=[False, True],
            format_func=lambda x: "🌍 Horários locais (padrão SSIM)" if not x else "🇧🇷 Converter tudo para horário de Brasília (UTC-3)",
            help="Escolha se quer manter os horários locais de cada aeroporto ou converter todos para o horário de Brasília"
        )
        
        if converter_horarios:
            st.info("⚠️ **Atenção:** Os horários serão convertidos para UTC-3 (Brasília). Verifique se esta é a opção desejada.")
        
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
        st.markdown("### ℹ️ Sobre os dados")
        st.markdown("""
        **📍 Horários locais:** Cada aeroporto mantém seu fuso horário original (padrão SSIM internacional).
        
        **🇧🇷 Horário de Brasília:** Todos os horários convertidos para UTC-3 (facilita análises nacionais).
        
        **🕐 Formato:** HHMM seguido do offset UTC (ex: 1430-0300 = 14:30 UTC-3)
        
        **📊 Fonte:** API SIROS - ANAC  
        **📋 Formato:** SSIM (IATA Standard)  
        **🔄 Atualização:** Dados em tempo real  
        
        [📖 Documentação SSIM](https://www.iata.org/en/publications/manuals/ssim/)
        """)
    
    # Área principal - Layout de coluna única
    if 'dados_api' in st.session_state and st.session_state['dados_api']:
        st.success(f"📊 **Dados carregados para temporada:** {st.session_state.get('temporada_atual', 'N/A')}")
        st.info(f"📈 **Total de registros:** {len(st.session_state['dados_api'])}")
        
        # Seleção da companhia
        if 'companhias_disponveis' in st.session_state:
            st.subheader("🏢 Selecionar Companhia Aérea")
            
            companhias = st.session_state['companhias_disponveis']
            
            # Criar lista com nome da companhia (se disponível no CSV) + opção "TODAS"
            df_airlines = carregar_dados_airlines()
            opcoes_companhias = ["TODAS - Todas as companhias (malha completa)"]
            codigos_companhias = ["TODAS"]
            
            for codigo in companhias:
                nome_cia = "Nome não encontrado"
                if df_airlines is not None:
                    resultado = df_airlines[df_airlines['IATA Designator'] == codigo]
                    if not resultado.empty:
                        nome_cia = resultado.iloc[0]['Airline Name']
                opcoes_companhias.append(f"{codigo} - {nome_cia}")
                codigos_companhias.append(codigo)
            
            # Estatísticas das companhias
            st.markdown(f"**📋 {len(companhias)} companhias disponíveis na temporada {st.session_state.get('temporada_atual', 'N/A')}**")
            
            companhia_selecionada = st.selectbox(
                "Escolha a companhia aérea:",
                options=range(len(opcoes_companhias)),
                format_func=lambda x: opcoes_companhias[x],
                help="Selecione uma companhia específica ou 'TODAS' para baixar a malha completa"
            )
            
            if companhia_selecionada is not None:
                codigo_selecionado = codigos_companhias[companhia_selecionada]
                
                # Carregar dados de aeroportos para conversão
                df_airports = carregar_dados_airports()
                
                # Filtrar dados
                dados_filtrados = filtrar_dados_por_companhia(
                    st.session_state['dados_api'], 
                    codigo_selecionado,
                    converter_horarios,
                    df_airports
                )
                
                st.success(f"✅ **Dados filtrados para {opcoes_companhias[companhia_selecionada]}**")
                st.info(f"📊 **Linhas encontradas:** {len(dados_filtrados)}")
                
                if converter_horarios:
                    st.info("🇧🇷 **Horários convertidos para horário de Brasília (UTC-3)**")
                else:
                    st.info("🌍 **Horários mantidos em fuso local de cada aeroporto**")
                
                # Preview dos dados
                if dados_filtrados:
                    with st.expander("👀 Preview dos dados (primeiras 10 linhas)"):
                        for i, linha in enumerate(dados_filtrados[:10]):
                            st.code(linha, language="text")
                    
                    # Estatísticas adicionais se for "TODAS"
                    if codigo_selecionado == "TODAS":
                        # Contar voos por companhia
                        contagem_por_cia = {}
                        for linha in dados_filtrados:
                            if linha.startswith('3 ') and len(linha) > 5:
                                cia = linha[2:4].strip()
                                contagem_por_cia[cia] = contagem_por_cia.get(cia, 0) + 1
                        
                        with st.expander("📊 Estatísticas por companhia"):
                            for cia, count in sorted(contagem_por_cia.items()):
                                nome_cia = "Nome não encontrado"
                                if df_airlines is not None:
                                    resultado = df_airlines[df_airlines['IATA Designator'] == cia]
                                    if not resultado.empty:
                                        nome_cia = resultado.iloc[0]['Airline Name']
                                st.write(f"**{cia}** - {nome_cia}: {count} voos")
                
                # Botão de download
                if dados_filtrados:
                    conteudo_ssim = "\n".join(dados_filtrados)
                    nome_arquivo = gerar_nome_arquivo(
                        codigo_selecionado, 
                        st.session_state.get('temporada_atual', 'UNK'),
                        converter_horarios
                    )
                    
                    st.download_button(
                        label="📥 Baixar arquivo SSIM",
                        data=conteudo_ssim.encode('latin-1'),
                        file_name=nome_arquivo,
                        mime="text/plain",
                        help=f"Baixar arquivo SSIM filtrado para {opcoes_companhias[companhia_selecionada]}",
                        use_container_width=True
                    )
    
    else:
        st.info("👈 Use o painel lateral para carregar os dados da API")
        
        # Informações sobre o sistema
        st.markdown("""
        ## 📖 Como usar:
        
        1. **Digite a temporada** no campo lateral (ex: W25, S25)
        2. **Escolha o formato de horários** (local ou Brasília)
        3. **Clique em "Carregar Dados"** para consultar a API da ANAC
        4. **Selecione a companhia aérea** desejada na lista ou "TODAS" para malha completa
        5. **Faça o download** do arquivo SSIM personalizado
        
        ## ℹ️ Sobre os dados:
        
        - **📍 Horários locais:** Fuso local de cada aeroporto (padrão SSIM)
        - **🇧🇷 Horário de Brasília:** Todos convertidos para UTC-3
        - **📊 Fonte:** API SIROS da ANAC
        - **📋 Formato:** SSIM (Standard Schedules Information Manual)
        - **💾 Encoding:** Latin-1 (padrão para arquivos SSIM)
        - **🔄 Conteúdo:** Malha aérea filtrada por companhia ou completa
        
        ## 🔗 Links úteis:
        
        - [API ANAC](https://sas.anac.gov.br/sas/siros_api/ssimfile)
        - [Formato SSIM](https://www.iata.org/en/publications/manuals/ssim/)
        """)

if __name__ == "__main__":
    main() 
