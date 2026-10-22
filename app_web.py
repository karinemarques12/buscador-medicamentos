import streamlit as st
import sqlite3
import pandas as pd
import os
import requests
import math

# Configuração da página do site (Modo Wide / largura total)
st.set_page_config(page_title="Buscador de Medicamentos - SPB", page_icon="💊", layout="wide")

# Cabeçalho centralizado com os logotipos
col_logo1, col_titulo, col_logo2 = st.columns([1, 4, 1])

with col_logo1:
    if os.path.exists("logo_prefeitura.png"):
        st.image("logo_prefeitura.png", width=200)
    else:
        st.warning("Logo Prefeitura não encontrada na pasta.")

with col_titulo:
    st.markdown("<h2 style='text-align: center; color: #1e293b; margin-top: 5px;'>💊 Buscador de Medicamentos - Santana de Parnaíba (SP)</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748b; font-size: 0.95em; margin-bottom: 0px;'>Consulta de preços de referência (PMC), genéricos, similares e medicamentos disponibilizados pelo SUS na rede municipal de Santana de Parnaíba.</p>", unsafe_allow_html=True)

with col_logo2:
    if os.path.exists("logo_sus.png"):
        st.image("logo_sus.png", width=130)
    else:
        st.warning("Logo SUS não encontrada na pasta.")

st.markdown("---")

# Função para carregar sugestões do banco
@st.cache_data
def carregar_sugestoes():
    try:
        conexao = sqlite3.connect("medicamentos.db")
        query = "SELECT DISTINCT substancia FROM produtos WHERE substancia IS NOT NULL UNION SELECT DISTINCT marca FROM produtos WHERE marca IS NOT NULL"
        df = pd.read_sql(query, conexao)
        conexao.close()
        return sorted(df.iloc[:, 0].dropna().tolist())
    except:
        return []

sugestoes_globais = carregar_sugestoes()

# LEGENDA ACIMA DA BUSCA
st.markdown(
    """
    <div style="background-color: #f1f5f9; padding: 10px 15px; border-radius: 8px; margin-bottom: 15px; border: 1px solid #e2e8f0;">
        <span style="font-weight: bold; color: #334155; margin-right: 15px;">LEGENDA:</span>
        <span style="color: #166534; font-weight: bold; margin-right: 15px;">🟢 Gratuito (Rede Pública) / Baixo Custo</span>
        <span style="color: #854d0e; font-weight: bold; margin-right: 15px;">🟡 Custo Intermediário</span>
        <span style="color: #991b1b; font-weight: bold; margin-right: 15px;">🔴 Custo Elevado</span>
        <br><span style="color: #64748b; font-size: 0.85em; font-style: italic;">* PMC: Preço Máximo ao Consumidor estabelecido pela CMED/Anvisa.</span>
    </div>
    """,
    unsafe_allow_html=True
)

# Campo de pesquisa unificado de medicamentos
termo = st.selectbox(
    "Digite ou selecione o nome do medicamento ou substância:",
    options=[""] + sugestoes_globais,
    index=0,
    help="Comece a digitar para filtrar as opções de marcas, genéricos ou substâncias."
)

termo_busca = termo.strip().upper()

if st.button("Pesquisar", type="primary") or termo_busca:
    if not termo_busca:
        st.warning("Por favor, selecione ou digite um medicamento.")
    else:
        try:
            conexao = sqlite3.connect("medicamentos.db")
            
            query = """
                SELECT substancia, marca, apresentacao, laboratorio, preco, na_remume, marca_limpa, substancia_limpa 
                FROM produtos 
                WHERE substancia_limpa IN (
                    SELECT DISTINCT substancia_limpa 
                    FROM produtos 
                    WHERE substancia_limpa LIKE ? OR marca_limpa LIKE ?
                )
                ORDER BY 
                    na_remume DESC, 
                    CASE WHEN preco = 0 THEN 999999 ELSE preco END ASC
            """
            
            param_search = f"%{termo_busca}%"
            df = pd.read_sql(query, conexao, params=(param_search, param_search))
            conexao.close()

            if df.empty:
                st.info("Nenhum medicamento encontrado com esse termo.")
            else:
                precos_validos = df[(df['na_remume'] == 0) & (df['preco'] > 0)]['preco']
                p33 = precos_validos.quantile(0.33) if not precos_validos.empty else 0
                p66 = precos_validos.quantile(0.66) if not precos_validos.empty else 0

                resultados_formatados = []
                cores_linhas = []

                for _, row in df.iterrows():
                    preco = row['preco']
                    na_remume = row['na_remume']
                    
                    if na_remume == 1:
                        preco_str = "Gratuito"
                        disp_str = "🟢 Disponível na rede pública"
                        cor_fundo = "#dcfce7"
                    else:
                        if preco > 0:
                            preco_str = f"R$ {preco:.2f}"
                            if preco <= p33:
                                disp_str = "Particular (Preço Baixo)"
                                cor_fundo = "#dcfce7"
                            elif preco <= p66:
                                disp_str = "Particular (Preço Intermediário)"
                                cor_fundo = "#fef9c3"
                            else:
                                disp_str = "Particular (Preço Elevado)"
                                cor_fundo = "#fee2e2"
                        else:
                            preco_str = "Não informado"
                            disp_str = "Particular"
                            cor_fundo = "#fef9c3"

                    resultados_formatados.append({
                        "Substância": row['substancia'],
                        "Marca": row['marca'],
                        "Apresentação": row['apresentacao'],
                        "Laboratório": row['laboratorio'],
                        "Preço (PMC)": preco_str,
                        "Disponibilidade": disp_str
                    })
                    cores_linhas.append(cor_fundo)

                df_exibicao = pd.DataFrame(resultados_formatados)

                def colorir_tabela(row):
                    cor = cores_linhas[row.name]
                    return [f'background-color: {cor}; color: #1e293b; text-align: left;' for _ in row]

                df_estilizado = df_exibicao.style.apply(colorir_tabela, axis=1)

                st.markdown(
                    """
                    <style>
                        iframe { width: 100% !important; }
                        div[data-testid="stDataFrame"] { width: 100% !important; }
                        table { width: 100% !important; table-layout: auto !important; }
                        th, td { white-space: normal !important; word-wrap: break-word !important; }
                    </style>
                    """,
                    unsafe_allow_html=True
                )

                st.dataframe(df_estilizado, use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"Erro ao consultar o banco de dados: {e}")

# --- SEÇÃO DE LOCAIS DE RETIRADA E BUSCA POR CEP COM COORDENADAS PRÉ-DEFINIDAS ---
st.markdown("---")
st.markdown("### 📍 Onde Encontrar / Locais de Atendimento e Proximidade")

tab_cep, tab_pub, tab_part = st.tabs(["🔍 Buscar por CEP Próximo", "🏥 Rede Pública (UBS)", "🛒 Farmácias Particulares"])

excel_file = "Farmacias Particular e Rede Pública.xlsx"

if os.path.exists(excel_file):
    try:
        df_part_excel = pd.read_excel(excel_file, sheet_name="Particular", skiprows=2)
        df_pub_excel = pd.read_excel(excel_file, sheet_name="Rede Publica", skiprows=3)

        # Coordenadas geográficas aproximadas fixas para cada UBS e Farmácia de Santana de Parnaíba / região
        # Isso elimina a lentidão de chamadas múltiplas à API de mapas em tempo de execução
        coords_ubs = {
            "UBS Alphaville/Tamboré": (-23.4795, -46.8521),
            "UBS Chácara das Garças": (-23.4412, -46.9155),
            "UBS Colinas da Anhanguera": (-23.4215, -46.8832),
            "UBS Dra. Roseli Folchini Boross": (-23.4350, -46.9420),
            "UBS Diego de Lima Camilo": (-23.4480, -46.9310),
            "UBS Dr. Álvaro Ribeiro": (-23.4420, -46.9200),
            "UBS Limério Cardoso Borchat": (-23.4390, -46.9180),
            "UBS Ingaí": (-23.4100, -46.9500),
            "UBS Sítio do Morro": (-23.4500, -46.9600)
        }

        coords_farmacias = {
            "Farma Med": (-23.4385, -46.9190),
            "Drogaria São Paulo": (-23.4380, -46.9185), # Fazendinha
            "Farmais Drogarias": (-23.4400, -46.9210),
            "Drogaria Estrela Dalva": (-23.4350, -46.9120),
            "Drogasil": (-23.4780, -46.8480),
            "Campeão Farma": (-23.4370, -46.9170),
            "Campeão Farma Santa Ana": (-23.4410, -46.9205),
            "Drogaria Leal": (-23.4300, -46.9000),
            "Farmácia Santana de Parnaíba - Saúde Farma": (-23.4405, -46.9195),
            "Farma Ponte": (-23.4395, -46.9188),
            "Drogaria São Luis": (-23.4402, -46.9212),
            "Farma Santana 1 - FarmaEduardo": (-23.4500, -46.9100),
            "Drogaria Saúde Farma": (-23.4600, -46.9700),
            "Drogaria Rede Mais Brasi": (-23.4400, -46.9190),
            "Farma 10 - Fazendinha": (-23.4388, -46.9192),
            "Droga Raia": (-23.4750, -46.8500),
            "Drogaria Bem Estar - Unidade 1": (-23.4590, -46.9680),
            "Farma Mais Vida": (-23.4580, -46.9650),
            "ULTRAFARMA POPULAR CAJAMAR": (-23.3850, -46.8850),
            "Drogaria Ipês": (-23.3830, -46.8820),
            "Pharma Apoio": (-23.4800, -46.8550),
            "Drogaria Far Márcia": (-23.4250, -46.8900),
            "Drogaria Capricórnio": (-23.4510, -46.9110),
            "Farmácia Farmatotal": (-23.4520, -46.9125)
        }

        with tab_cep:
            st.markdown("#### Encontre os locais mais próximos digitando seu CEP")
            
            with st.form(key="form_cep"):
                cep_input = st.text_input("Digite seu CEP (apenas números e aperte ENTER):", max_chars=9, placeholder="Ex: 06533-205")
                submit_cep = st.form_submit_button("Buscar por CEP", type="primary")

            if submit_cep:
                cep_limpo = "".join(filter(str.isdigit, cep_input))
                if len(cep_limpo) != 8:
                    st.warning("Por favor, digite um CEP válido com 8 dígitos.")
                else:
                    try:
                        url_viacep = f"https://viacep.com.br/ws/{cep_limpo}/json/"
                        req_viacep = requests.get(url_viacep, timeout=5)
                        
                        if req_viacep.status_code != 200:
                            st.error("Serviço de consulta de CEP indisponível no momento.")
                        else:
                            resp = req_viacep.json()
                            if "erro" in resp:
                                st.error("CEP não encontrado. Verifique o número digitado.")
                            else:
                                rua = resp.get('logradouro', '')
                                bairro = resp.get('bairro', '')
                                cidade = resp.get('localidade', '')
                                uf = resp.get('uf', '')
                                
                                st.success(f"📍 **Endereço encontrado:** {rua}, {bairro} - {cidade}/{uf}")
                                
                                # Geocodifica APENAS o CEP do usuário (1 única requisição rápida)
                                query_geo = f"{rua}, {bairro}, {cidade}, {uf}, Brasil"
                                url_nominatim = f"https://nominatim.openstreetmap.org/search?q={requests.utils.quote(query_geo)}&format=json&limit=1"
                                headers = {'User-Agent': 'BuscadorMedicamentosParnaiba/1.0'}
                                
                                lat_usuario, lon_usuario = None, None
                                try:
                                    geo_req = requests.get(url_nominatim, headers=headers, timeout=4)
                                    if geo_req.status_code == 200 and geo_req.json():
                                        geo_data = geo_req.json()
                                        lat_usuario = float(geo_data[0]['lat'])
                                        lon_usuario = float(geo_data[0]['lon'])
                                    else:
                                        # Fallback para bairro/cidade se rua exata não achar
                                        query_fallback = f"{bairro}, {cidade}, {uf}, Brasil"
                                        url_fall = f"https://nominatim.openstreetmap.org/search?q={requests.utils.quote(query_fallback)}&format=json&limit=1"
                                        fall_req = requests.get(url_fall, headers=headers, timeout=4)
                                        if fall_req.status_code == 200 and fall_req.json():
                                            lat_usuario = float(fall_req.json()[0]['lat'])
                                            lon_usuario = float(fall_req.json()[0]['lon'])
                                        else:
                                            # Coordenada padrão de Santana de Parnaíba caso falhe
                                            lat_usuario, lon_usuario = -23.4431, -46.9175
                                except:
                                    lat_usuario, lon_usuario = -23.4431, -46.9175

                                def calcular_distancia(lat1, lon1, lat2, lon2):
                                    R = 6371
                                    dlat = math.radians(lat2 - lat1)
                                    dlon = math.radians(lon2 - lon1)
                                    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
                                    c = 2 * math.asin(math.sqrt(a))
                                    return R * c

                                st.markdown("---")
                                st.markdown("##### 🏥 UBSs Mais Próximas:")
                                ubs_proximas = []
                                for _, row in df_pub_excel.iterrows():
                                    nome_loc = str(row['Nome']).strip()
                                    lat2, lon2 = coords_ubs.get(nome_loc, (-23.4431, -46.9175))
                                    dist = calcular_distancia(lat_usuario, lon_usuario, lat2, lon2)
                                    ubs_proximas.append((dist, row))
                                
                                ubs_proximas.sort(key=lambda x: x[0])
                                for dist, row in ubs_proximas[:3]:
                                    dist_str = f" (~{dist:.1f} km)"
                                    link_end = f"[{row['Endereço']}]({row['Link localização']})" if str(row['Link localização']).startswith("http") else row['Endereço']
                                    st.markdown(f"- **{row['Nome']}**{dist_str}  \n  📍 {link_end}  \n  📞 {row['Telefone de Contato']}")

                                st.markdown("##### 🛒 Farmácias Particulares Mais Próximas:")
                                farm_proximas = []
                                for _, row in df_part_excel.iterrows():
                                    nome_loc = str(row['Nome']).strip()
                                    # Procura nas coordenadas conhecidas ou usa padrão central de Parnaíba
                                    lat2, lon2 = coords_farmacias.get(nome_loc, (-23.4431, -46.9175))
                                    dist = calcular_distancia(lat_usuario, lon_usuario, lat2, lon2)
                                    farm_proximas.append((dist, row))
                                
                                farm_proximas.sort(key=lambda x: x[0])
                                for dist, row in farm_proximas[:5]:
                                    dist_str = f" (~{dist:.1f} km)"
                                    site = str(row['Site']).strip() if pd.notna(row['Site']) and str(row['Site']).strip() != 'nan' else None
                                    nome_exib = f"[{row['Nome']}]({site})" if site and site.startswith("http") else row['Nome']
                                    link_end = f"[{row['Endereço']}]({row['Link localização']})" if str(row['Link localização']).startswith("http") else row['Endereço']
                                    st.markdown(f"- **{nome_exib}**{dist_str}  \n  📍 {link_end}  \n  📞 {row['Telefone de Contato']}")
                    except Exception as err:
                        st.error(f"Erro ao processar a busca por CEP: {err}")

        with tab_pub:
            st.markdown(f"#### Unidades Básicas de Saúde (UBS) - Rede Municipal")
            for _, row in df_pub_excel.iterrows():
                nome = str(row['Nome']).strip()
                end = str(row['Endereço']).strip()
                link = str(row['Link localização']).strip()
                tel = str(row['Telefone de Contato']).strip()
                
                link_end = f"[{end}]({link})" if link.startswith("http") else end
                st.markdown(f"- **{nome}**  \n  📍 **Endereço:** {link_end}  \n  📞 **Telefone:** {tel}")

        with tab_part:
            st.markdown(f"#### Farmácias e Drogarias Particulares")
            for _, row in df_part_excel.iterrows():
                nome = str(row['Nome']).strip()
                end = str(row['Endereço']).strip()
                link = str(row['Link localização']).strip()
                tel = str(row['Telefone de Contato']).strip()
                site = str(row['Site']).strip() if pd.notna(row['Site']) and str(row['Site']).strip() != 'nan' else None

                nome_exib = f"[{nome}]({site})" if site and site.startswith("http") else nome
                link_end = f"[{end}]({link})" if link.startswith("http") else end
                
                st.markdown(f"- **{nome_exib}**  \n  📍 **Endereço:** {link_end}  \n  📞 **Telefone:** {tel}")

    except Exception as e:
        st.error(f"Erro ao carregar o arquivo Excel de locais: {e}")
else:
    st.info("Arquivo 'Farmacias Particular e Rede Pública.xlsx' não encontrado no diretório do projeto.")