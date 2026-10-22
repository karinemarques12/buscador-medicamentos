import streamlit as st
import sqlite3
import pandas as pd
import os
import requests
import math

# Configuração da página do site (Modo Wide / largura total)
st.set_page_config(page_title="💊 Buscador de Medicamentos - Santana de Parnaíba", page_icon="💊", layout="wide")

# Cabeçalho centralizado com os logotipos
col_logo1, col_titulo, col_logo2 = st.columns([1, 4, 1])

with col_logo1:
    if os.path.exists("logo_prefeitura.png"):
        st.image("logo_prefeitura.png", width=200)
    else:
        st.warning("Logo Prefeitura não encontrada na pasta.")

with col_titulo:
    st.markdown("<h2 style='text-align: center; color: #1e293b; margin-top: 5px;'>💊 Buscador de Medicamentos - Santana de Parnaíba</h2>", unsafe_allow_html=True)
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

# LEGENDA ACIMA DA BUSCA (SEM O TERMO REMUME)
st.markdown(
    """
    <div style="background-color: #f1f5f9; padding: 10px 15px; border-radius: 8px; margin-bottom: 15px; border: 1px solid #e2e8f0;">
        <span style="font-weight: bold; color: #334155; margin-right: 15px;">LEGENDA:</span>
        <span style="color: #166534; font-weight: bold; margin-right: 15px;">🟢 Gratuito / Rede Pública / Baixo Custo</span>
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

# --- SEÇÃO DE LOCAIS DE RETIRADA E BUSCA POR CEP ---
st.markdown("---")
st.markdown("### 📍 Onde Encontrar / Locais de Atendimento e Proximidade")

# CEP PRIMEIRO, SEGUIDO DA REDE PÚBLICA E FARMÁCIAS PARTICULARES
tab_cep, tab_pub, tab_part = st.tabs(["🔍 Buscar por CEP Próximo", "🏥 Rede Pública (UBS)", "🛒 Farmácias Particulares"])

excel_file = "Farmacias Particular e Rede Pública.xlsx"

if os.path.exists(excel_file):
    try:
        df_part_excel = pd.read_excel(excel_file, sheet_name="Particular", skiprows=2)
        df_pub_excel = pd.read_excel(excel_file, sheet_name="Rede Publica", skiprows=3)

        with tab_cep:
            st.markdown("#### Encontre os locais mais próximos digitando seu CEP")
            cep_input = st.text_input("Digite seu CEP (apenas números):", max_chars=8, placeholder="Ex: 06533205")
            
            if st.button("Buscar por CEP"):
                cep_limpo = "".join(filter(str.isdigit, cep_input))
                if len(cep_limpo) != 8:
                    st.warning("Por favor, digite um CEP válido com 8 dígitos.")
                else:
                    url_viacep = f"https://viacep.com.br/ws/{cep_limpo}/json/"
                    resp = requests.get(url_viacep).json()
                    
                    if "erro" in resp:
                        st.error("CEP não encontrado. Verifique o número digitado.")
                    else:
                        rua = resp.get('logradouro', '')
                        bairro = resp.get('bairro', '')
                        cidade = resp.get('localidade', '')
                        uf = resp.get('uf', '')
                        
                        st.success(f"📍 **Endereço encontrado:** {rua}, {bairro} - {cidade}/{uf}")
                        
                        query_geo = f"{rua}, {bairro}, {cidade}, {uf}, Brasil"
                        url_nominatim = f"https://nominatim.openstreetmap.org/search?q={requests.utils.quote(query_geo)}&format=json&limit=1"
                        headers = {'User-Agent': 'BuscadorMedicamentosParnaiba/1.0'}
                        
                        geo_resp = requests.get(url_nominatim, headers=headers).json()
                        
                        lat_usuario, lon_usuario = None, None
                        if geo_resp:
                            lat_usuario = float(geo_resp[0]['lat'])
                            lon_usuario = float(geo_resp[0]['lon'])
                        else:
                            query_geo_fallback = f"{bairro}, {cidade}, {uf}, Brasil"
                            url_fallback = f"https://nominatim.openstreetmap.org/search?q={requests.utils.quote(query_geo_fallback)}&format=json&limit=1"
                            geo_fall_resp = requests.get(url_fallback, headers=headers).json()
                            if geo_fall_resp:
                                lat_usuario = float(geo_fall_resp[0]['lat'])
                                lon_usuario = float(geo_fall_resp[0]['lon'])

                        def calcular_distancia(lat1, lon1, endereco_str):
                            if lat1 is None or lon1 is None:
                                return 9999
                            try:
                                url_loc = f"https://nominatim.openstreetmap.org/search?q={requests.utils.quote(endereco_str + ', Santana de Parnaíba, SP, Brasil')}&format=json&limit=1"
                                r_loc = requests.get(url_loc, headers=headers).json()
                                if r_loc:
                                    lat2 = float(r_loc[0]['lat'])
                                    lon2 = float(r_loc[0]['lon'])
                                    
                                    R = 6371
                                    dlat = math.radians(lat2 - lat1)
                                    dlon = math.radians(lon2 - lon1)
                                    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
                                    c = 2 * math.asin(math.sqrt(a))
                                    return R * c
                            except:
                                pass
                            return 9999

                        st.markdown("---")
                        st.markdown("##### 🏥 UBSs Mais Próximas:")
                        ubs_proximas = []
                        for _, row in df_pub_excel.iterrows():
                            dist = calcular_distancia(lat_usuario, lon_usuario, str(row['Endereço'])) if lat_usuario else 0
                            ubs_proximas.append((dist, row))
                        
                        ubs_proximas.sort(key=lambda x: x[0])
                        for dist, row in ubs_proximas[:3]:
                            dist_str = f" (~{dist:.1f} km)" if dist != 9999 else ""
                            link_end = f"[{row['Endereço']}]({row['Link localização']})" if str(row['Link localização']).startswith("http") else row['Endereço']
                            st.markdown(f"- **{row['Nome']}**{dist_str}  \n  📍 {link_end}  \n  📞 {row['Telefone de Contato']}")

                        st.markdown("##### 🛒 Farmácias Particulares Mais Próximas:")
                        farm_proximas = []
                        for _, row in df_part_excel.iterrows():
                            dist = calcular_distancia(lat_usuario, lon_usuario, str(row['Endereço'])) if lat_usuario else 0
                            farm_proximas.append((dist, row))
                        
                        farm_proximas.sort(key=lambda x: x[0])
                        for dist, row in farm_proximas[:5]:
                            dist_str = f" (~{dist:.1f} km)" if dist != 9999 else ""
                            site = str(row['Site']).strip() if pd.notna(row['Site']) and str(row['Site']).strip() != 'nan' else None
                            nome_exib = f"[{row['Nome']}]({site})" if site and site.startswith("http") else row['Nome']
                            link_end = f"[{row['Endereço']}]({row['Link localização']})" if str(row['Link localização']).startswith("http") else row['Endereço']
                            st.markdown(f"- **{nome_exib}**{dist_str}  \n  📍 {link_end}  \n  📞 {row['Telefone de Contato']}")

        with tab_pub:
            st.markdown(f"#### Unidades Básicas de Saúde (UBS) - Rede Municipal ({len(df_pub_excel)} locais)")
            for _, row in df_pub_excel.iterrows():
                nome = str(row['Nome']).strip()
                end = str(row['Endereço']).strip()
                link = str(row['Link localização']).strip()
                tel = str(row['Telefone de Contato']).strip()
                
                link_end = f"[{end}]({link})" if link.startswith("http") else end
                st.markdown(f"- **{nome}**  \n  📍 **Endereço:** {link_end}  \n  📞 **Telefone:** {tel}")

        with tab_part:
            st.markdown(f"#### Farmácias e Drogarias Particulares ({len(df_part_excel)} locais)")
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