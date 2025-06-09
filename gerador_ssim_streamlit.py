# -*- coding: utf-8 -*-
# Gerador SSIM - ANAC API
# Versão: 1.0.05
# Data: 2025-06-09
# Changelog:
# v1.0.01 - Correção do espaçamento na repetição do código da companhia aérea
# v1.0.02 - Correção formato SSIM: 4 linhas zeros, numeração sequencial, linha 5 correta
# v1.0.03 - Correção data + 4 linhas zeros entre linha 1 e 2 + melhoria campos linha 3
# v1.0.04 - PRESERVAÇÃO 100% DADOS ORIGINAIS ANAC - removidas modificações nos campos
# v1.0.05 - ADAPTAÇÃO PADRÃO SSIM GOL - melhoria campos onward carriage e service information

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
    page_title="Gerador SSIM - ANAC API v1.0.05",
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

def ajustar_formato_ssim(linha_ssim):
    """Ajusta formato SSIM para repetir código da companhia aérea na posição específica"""
    if not linha_ssim.startswith('3 '):
        return linha_ssim
    
    try:
        # Extrair código da companhia (posições 2-4)
        codigo_cia = linha_ssim[2:4].strip()
        
        # Procurar o padrão no final: [muitos espaços] + codigo_cia + espaço + número
        # Exemplo: "                                                              AF 0415"
        
        # Procurar por 30+ espaços seguidos do código da CIA e número do voo
        padrao = f"( {{30,}}){codigo_cia} (\\d{{4}})"
        match = re.search(padrao, linha_ssim)
        
        if match:
            # Encontrou! Vamos substituir
            espacos_originais = match.group(1)  # Os espaços antes do código
            numero_voo = match.group(2)  # O número do voo
            
            # Remover 9 espaços e inserir "AF       " (AF + 7 espaços)
            if len(espacos_originais) >= 15:  # Garantir que tem espaços suficientes
                # Calcular: 62 espaços originais - 9 = 53 espaços antes do novo AF
                espacos_antes_novo_af = len(espacos_originais) - 9
                
                if espacos_antes_novo_af > 0:
                    # Construir: 53_espaços + AF + 7_espaços + AF_0415
                    novo_formato = f"{' ' * espacos_antes_novo_af}{codigo_cia}{' ' * 7}{codigo_cia} {numero_voo}"
                    
                    # Substituir na linha original
                    linha_ajustada = linha_ssim.replace(
                        f"{espacos_originais}{codigo_cia} {numero_voo}",
                        novo_formato
                    )
                    return linha_ajustada
        
        # Se não encontrou o padrão padrão, tentar abordagem mais geral
        # Procurar qualquer sequência longa de espaços
        match_espacos = re.search(r' {25,}', linha_ssim)
        if match_espacos:
            espacos_encontrados = match_espacos.group(0)
            
            # Verificar se após os espaços tem o código da CIA
            pos_fim_espacos = match_espacos.end()
            resto_linha = linha_ssim[pos_fim_espacos:]
            
            if resto_linha.startswith(f"{codigo_cia} "):
                # Encontrou! Fazer a substituição
                if len(espacos_encontrados) >= 15:
                    espacos_antes_novo_af = len(espacos_encontrados) - 9
                    
                    if espacos_antes_novo_af > 0:
                        novo_formato = f"{' ' * espacos_antes_novo_af}{codigo_cia}{' ' * 7}"
                        
                        linha_ajustada = linha_ssim.replace(
                            espacos_encontrados,
                            novo_formato
                        )
                        return linha_ajustada
        
        # Se não conseguiu ajustar, retorna original
        return linha_ssim
        
    except Exception as e:
        # Em caso de erro, retorna a linha original
        return linha_ssim

def converter_horario_ssim(linha_ssim, df_airports, para_brasilia=False):
    """Converte horários de uma linha SSIM para horário de Brasília"""
    if not linha_ssim.startswith('3 '):
        return linha_ssim
    
    # Primeiro ajustar o formato (repetir código da CIA)
    linha_ajustada = ajustar_formato_ssim(linha_ssim)
    
    # Se não precisa converter horários, retorna linha ajustada
    if not para_brasilia:
        return linha_ajustada
    
    # Extrair aeroportos da linha SSIM
    # Formato: 3 XX NNNNNNNJDDMMMYYDDMMMYYOOOOOOO  AAAHHMM-TTTT  BBBHHMM-TTTT  ...
    try:
        # Encontrar posições dos aeroportos e horários
        partes = linha_ajustada.split()
        
        # Buscar padrões de aeroporto + horário (ex: GRU12001200-0300)
        padrao_aeroporto_horario = re.findall(r'([A-Z]{3})(\d{4})(\d{4})([-+]\d{4})', linha_ajustada)
        
        linha_convertida = linha_ajustada
        
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
        # Se der qualquer erro, retorna a linha ajustada (sem conversão de horário)
        return linha_ajustada

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

def melhorar_campo_informacoes_linha3(linha_ssim):
    """
    Melhora o campo de informações adicionais da linha 3 seguindo padrão SSIM
    Exemplo: Y312 -> Y138VVG373G (baseado no padrão GOL)
    """
    if not linha_ssim.startswith('3 '):
        return linha_ssim
    
    # Extrair informações da linha
    codigo_cia = linha_ssim[2:4].strip()  # Posição 2-3: código da companhia
    
    # Encontrar posição do campo de aeronave (geralmente após os aeroportos e horários)
    # No formato SSIM, o tipo de aeronave está por volta da posição 100-110
    tipo_aeronave = ""
    for i in range(100, min(120, len(linha_ssim)-3)):
        if linha_ssim[i:i+3].strip() and linha_ssim[i:i+3].isalnum():
            tipo_aeronave = linha_ssim[i:i+3].strip()
            break
    
    # Localizar campo atual de informações (geralmente contém Y seguido de números)
    campo_info_atual = ""
    pos_campo_info = -1
    for i in range(150, min(180, len(linha_ssim)-10)):
        if linha_ssim[i] == 'Y' and linha_ssim[i+1:i+4].isdigit():
            # Encontrou campo que começa com Y seguido de números
            # Extrair até encontrar espaços ou fim
            j = i
            while j < len(linha_ssim) and linha_ssim[j] not in [' ', '\t']:
                j += 1
            campo_info_atual = linha_ssim[i:j]
            pos_campo_info = i
            break
    
    if pos_campo_info == -1:
        return linha_ssim  # Não encontrou campo para melhorar
    
    # Criar novo campo de informações baseado no padrão SSIM
    # Formato: Y + configuração + código aeronave + código companhia
    configuracao_base = campo_info_atual[1:] if len(campo_info_atual) > 1 else "312"
    
    # Se a configuração é muito curta, expandir baseada no tipo de aeronave
    if len(configuracao_base) < 3:
        configuracao_base = "312"  # Padrão básico
    
    # Criar campo melhorado: Y + config + aeronave_info + companhia
    if tipo_aeronave:
        # Adicionar informações como no padrão GOL: Y138VVG373G
        novo_campo_info = f"Y{configuracao_base}VV{tipo_aeronave}{codigo_cia}"
    else:
        # Padrão básico se não encontrar aeronave
        novo_campo_info = f"Y{configuracao_base}VV{codigo_cia}"
    
    # Substituir na linha, mantendo mesmo tamanho
    tamanho_original = len(campo_info_atual)
    if len(novo_campo_info) > tamanho_original:
        novo_campo_info = novo_campo_info[:tamanho_original]
    elif len(novo_campo_info) < tamanho_original:
        novo_campo_info = novo_campo_info + ' ' * (tamanho_original - len(novo_campo_info))
    
    linha_melhorada = linha_ssim[:pos_campo_info] + novo_campo_info + linha_ssim[pos_campo_info + tamanho_original:]
    
    return linha_melhorada

def adaptar_para_padrao_ssim_gol(linha_ssim):
    """
    Adapta dados da ANAC para padrão SSIM da GOL, melhorando campos obrigatórios
    """
    if not linha_ssim.startswith('3 '):
        return linha_ssim
    
    try:
        # Extrair informações básicas
        codigo_cia = linha_ssim[2:4].strip()
        
        # Encontrar posição do tipo de aeronave (geralmente posição ~105-115)
        tipo_aeronave = ""
        for i in range(100, min(120, len(linha_ssim)-3)):
            if linha_ssim[i:i+3].strip() and linha_ssim[i:i+3].isalnum():
                tipo_aeronave = linha_ssim[i:i+3].strip()
                break
        
        if not tipo_aeronave:
            tipo_aeronave = "320"  # Default
        
        # Melhoria 1: Campo Onward Carriage (posição ~120-140)
        # Formato ANAC: "LA 0707"
        # Formato GOL:  "G3       G3 1007"
        
        # Encontrar campo onward carriage atual
        padrao_onward = f"{codigo_cia} \\d{{4}}"
        match_onward = re.search(padrao_onward, linha_ssim)
        
        if match_onward:
            campo_onward_original = match_onward.group(0)
            numero_voo = campo_onward_original.split()[1]
            
            # Criar novo campo no padrão GOL: "G3       G3 1007"
            novo_campo_onward = f"{codigo_cia}{' ' * 7}{codigo_cia} {numero_voo}"
            
            # Localizar posição para substituição
            pos_onward = linha_ssim.find(campo_onward_original)
            if pos_onward > 0:
                # Calcular espaços antes para manter 200 caracteres
                espacos_antes = 120  # Posição aproximada do campo onward
                linha_parte1 = linha_ssim[:espacos_antes]
                linha_parte2 = linha_ssim[pos_onward + len(campo_onward_original):]
                
                # Reconstruir linha
                linha_ssim = linha_parte1 + novo_campo_onward + linha_parte2
        
        # Melhoria 2: Campo Service Information (posição ~170-190)
        # Formato ANAC: "000"
        # Formato GOL:  "Y138VVG373G"
        
        # Procurar campo de service information (geralmente "000" ou "Y...")
        padrao_service = r'(000|Y\d+)'
        match_service = re.search(padrao_service, linha_ssim[150:])
        
        if match_service:
            campo_service_original = match_service.group(0)
            
            # Criar novo campo no padrão GOL
            if tipo_aeronave in ['73G', '73X', '738']:
                configuracao = "138" if tipo_aeronave == '73G' else "186"
            elif tipo_aeronave in ['320', '321', '319']:
                configuracao = "180" if tipo_aeronave == '320' else "224"
            elif tipo_aeronave in ['789', '788']:
                configuracao = "304"
            else:
                configuracao = "180"  # Default
            
            novo_campo_service = f"Y{configuracao}VV{tipo_aeronave}{codigo_cia}"
            
            # Localizar e substituir
            pos_service = linha_ssim.rfind(campo_service_original)
            if pos_service > 0:
                linha_antes = linha_ssim[:pos_service]
                linha_depois = linha_ssim[pos_service + len(campo_service_original):]
                linha_ssim = linha_antes + novo_campo_service + linha_depois
        
        # Garantir 200 caracteres exatos
        if len(linha_ssim) > 200:
            linha_ssim = linha_ssim[:200]
        elif len(linha_ssim) < 200:
            linha_ssim = linha_ssim + ' ' * (200 - len(linha_ssim))
        
        return linha_ssim
        
    except Exception:
        # Em caso de erro, retorna linha original
        return linha_ssim

def filtrar_dados_por_companhia(dados_json, codigo_companhia, converter_para_brasilia=False, df_airports=None, adaptar_ssim_gol=False):
    """Filtra dados SSIM por código da companhia aérea com opção de adaptação para padrão SSIM GOL"""
    linhas_filtradas = []
    linhas_header = []
    
    # Separar headers e linhas de dados
    for item in dados_json:
        if isinstance(item, dict) and 'ssimfile' in item:
            linha = item['ssimfile']
            if linha:
                # Headers (linhas que começam com 1, 2, ou são zeros)
                if linha.startswith(('1', '2')):
                    linhas_header.append(linha)
                elif linha.startswith('0'):
                    # Pular linhas de zeros do header original
                    continue
                # Dados de voos (linhas que começam com 3)
                elif linha.startswith('3 ') and len(linha) > 5:
                    if codigo_companhia == "TODAS":
                        # Se for "TODAS", incluir todas as linhas
                        linha_processada = linha  # ✅ DADOS ORIGINAIS DA ANAC
                        
                        # Aplicar conversões se solicitadas
                        if converter_para_brasilia:
                            linha_processada = converter_horario_ssim(linha_processada, df_airports, True)
                        
                        if adaptar_ssim_gol:
                            linha_processada = adaptar_para_padrao_ssim_gol(linha_processada)
                        
                        linhas_filtradas.append(linha_processada)
                    else:
                        # Filtrar por companhia específica
                        codigo_linha = linha[2:4].strip()
                        if codigo_linha == codigo_companhia:
                            linha_processada = linha  # ✅ DADOS ORIGINAIS DA ANAC
                            
                            # Aplicar conversões se solicitadas
                            if converter_para_brasilia:
                                linha_processada = converter_horario_ssim(linha_processada, df_airports, True)
                            
                            if adaptar_ssim_gol:
                                linha_processada = adaptar_para_padrao_ssim_gol(linha_processada)
                            
                            linhas_filtradas.append(linha_processada)
    
    # Agora vamos gerar o arquivo SSIM com formato correto
    resultado = []
    numero_linha = 1
    
    # Adicionar headers existentes com zeros entre linha 1 e 2
    for i, header in enumerate(linhas_header):
        resultado.append(header)
        numero_linha += 1
        
        # Se for a primeira linha (linha 1), adicionar 4 linhas de zeros
        if i == 0:  # Após a primeira linha (linha 1)
            for _ in range(4):
                zeros_line = "0" * 200
                resultado.append(zeros_line)
                numero_linha += 1
    
    # Adicionar linhas de dados com numeração sequencial corrigida
    for linha_data in linhas_filtradas:
        # ✅ PRESERVAR DADOS (com melhorias se solicitadas) - apenas renumerar
        nova_linha = linha_data[:192] + f"{numero_linha:08}"  # Últimos 8 caracteres são o número da linha
        resultado.append(nova_linha)
        numero_linha += 1
    
    # Adicionar 4 linhas de zeros antes da linha 5
    for _ in range(4):
        zeros_line = "0" * 200
        resultado.append(zeros_line)
        numero_linha += 1
    
    # Adicionar linha 5 (final) com data atual e numeração
    from datetime import datetime
    data_emissao = datetime.now().strftime("%d%b%y").upper()
    
    # Obter código da companhia para linha 5
    codigo_para_linha5 = codigo_companhia if codigo_companhia != "TODAS" else "XX"
    if len(codigo_para_linha5) > 2:
        codigo_para_linha5 = codigo_para_linha5[:2]
    
    linha_5_conteudo = f"5 {codigo_para_linha5} {data_emissao}"
    
    # Formato correto: número da última linha 3 + E + número da linha 5 atual
    # numero_linha já está na linha 5, então a última linha 3 foi numero_linha - 5 (4 zeros + linha 5)
    numero_ultima_linha3 = numero_linha - 5  # Última linha 3 antes dos 4 zeros
    numero_linha_str_e = f"{numero_ultima_linha3:06}E"
    numero_linha_str_final = f"{numero_linha:06}"
    
    # Calcular espaços para manter 200 caracteres
    espacos_necessarios = 200 - len(linha_5_conteudo) - len(numero_linha_str_e) - len(numero_linha_str_final)
    linha_5 = linha_5_conteudo + (' ' * espacos_necessarios) + numero_linha_str_e + numero_linha_str_final
    resultado.append(linha_5)
    
    return resultado

def gerar_nome_arquivo(codigo_companhia, temporada, horario_brasilia=False, padrao_gol=False):
    """Gera nome do arquivo baseado na companhia e temporada"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sufixo_horario = "_HORARIO_BRASILIA" if horario_brasilia else "_HORARIO_LOCAL"
    sufixo_padrao = "_PADRAO_SSIM_GOL" if padrao_gol else "_PADRAO_ANAC"
    
    if codigo_companhia == "TODAS":
        return f"ssim_TODAS_COMPANHIAS_{temporada}{sufixo_horario}{sufixo_padrao}_{timestamp}.ssim"
    else:
        return f"ssim_{codigo_companhia}_{temporada}{sufixo_horario}{sufixo_padrao}_{timestamp}.ssim"

# --- Interface Streamlit ---
def main():
    st.title("✈️ Gerador de Arquivos SSIM")
    st.markdown("### Extrair dados de malha aérea da API da ANAC")
    st.markdown("**Versão:** 1.0.05 | **Data:** 09/06/2025")
    
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
        
        # Nova opção: Padrão SSIM
        st.markdown("---")
        st.markdown("### ✈️ Padrão SSIM")
        
        padrao_ssim = st.radio(
            "Formato dos campos SSIM:",
            options=[False, True],
            format_func=lambda x: "📊 Dados originais ANAC (preservar 100%)" if not x else "🔧 Adaptar para padrão SSIM GOL (onward carriage + service info)",
            help="Escolha entre manter os dados exatamente como a ANAC envia ou adaptar para padrão SSIM da GOL"
        )
        
        if padrao_ssim:
            st.info("🔧 **Melhorias ativadas:**\n- Campo Onward Carriage: `G3       G3 1007`\n- Service Information: `Y138VVG373G`")
        else:
            st.info("📊 **Dados preservados:**\n- Campo Onward: `LA 0707`\n- Service Info: `000`")
        
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
        
        **🔧 Padrão SSIM GOL:** Adapta campos para formato compatível com sistemas SSIM padrão.
        
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
                    df_airports,
                    padrao_ssim  # Nova opção
                )
                
                st.success(f"✅ **Dados filtrados para {opcoes_companhias[companhia_selecionada]}**")
                st.info(f"📊 **Linhas encontradas:** {len(dados_filtrados)}")
                
                if converter_horarios:
                    st.info("🇧🇷 **Horários convertidos para horário de Brasília (UTC-3)**")
                else:
                    st.info("🌍 **Horários mantidos em fuso local de cada aeroporto**")
                
                if padrao_ssim:
                    st.info("🔧 **Dados adaptados para padrão SSIM GOL**")
                else:
                    st.info("📊 **Dados preservados no formato original ANAC**")
                
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
                    
                    # Botão para baixar
                    arquivo_ssim = "\n".join(dados_filtrados)
                    nome_arquivo = gerar_nome_arquivo(codigo_selecionado, st.session_state.get('temporada_atual', 'TEMP'), converter_horarios, padrao_ssim)
                    
                    st.download_button(
                        label="📥 Baixar Arquivo SSIM",
                        data=arquivo_ssim,
                        file_name=nome_arquivo,
                        mime="text/plain",
                        help="Clique para baixar o arquivo SSIM filtrado"
                    )
                    
                    # Informações do arquivo
                    st.markdown("---")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("📄 Total de linhas", len(dados_filtrados))
                    
                    with col2:
                        st.metric("💾 Tamanho aproximado", f"{len(arquivo_ssim) // 1024} KB")
                    
                    with col3:
                        if codigo_selecionado != "TODAS":
                            voos_dados = len([l for l in dados_filtrados if l.startswith('3 ')])
                            st.metric("✈️ Voos encontrados", voos_dados)
                else:
                    st.warning("⚠️ Nenhum dado encontrado para os filtros selecionados")
        else:
            st.warning("⚠️ Nenhuma companhia encontrada nos dados carregados")
    else:
        st.info("👆 **Para começar:** Digite uma temporada na barra lateral e clique em 'Carregar Dados da API'")
        
        st.markdown("---")
        st.markdown("### 📖 **Como usar:**")
        st.markdown("""
        1. **Digite a temporada** na barra lateral (ex: W25, S25)
        2. **Configure as opções** de horário e formato SSIM
        3. **Clique em 'Carregar Dados da API'** 
        4. **Selecione uma companhia** aérea
        5. **Baixe o arquivo SSIM** gerado
        """)

if __name__ == "__main__":
    main() 
