import streamlit as st
import sqlite3
import pandas as pd
import os

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

# LEGENDA ACIMA DA BUSCA
st.markdown(
    """
    <div style="background-color: #f1f5f9; padding: 10px 15px; border-radius: 8px; margin-bottom: 15px; border: 1px solid #e2e8f0;">
        <span style="font-weight: bold; color: #334155; margin-right: 15px;">LEGENDA:</span>
        <span style="color: #166534; font-weight: bold; margin-right: 15px;">🟢 Gratuito (REMUME / Rede Pública) / Baixo Custo</span>
        <span style="color: #854d0e; font-weight: bold; margin-right: 15px;">🟡 Custo Intermediário</span>
        <span style="color: #991b1b; font-weight: bold; margin-right: 15px;">🔴 Custo Elevado</span>
        <br><span style="color: #64748b; font-size: 0.85em; font-style: italic;">* PMC: Preço Máximo ao Consumidor estabelecido pela CMED/Anvisa.</span>
    </div>
    """,
    unsafe_allow_html=True
)

# Campo de pesquisa unificado
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
            
            # Busca os medicamentos equivalentes pela substância limpa
            query = """
                SELECT substancia, marca, apresentacao, laboratorio, preco, na_remume, marca_limpa, substancia_limpa 
                FROM produtos 
                WHERE substancia_limpa IN (
                    SELECT DISTINCT substancia_limpa 
                    FROM produtos 
                    WHERE substancia_limpa LIKE ? OR marca_limpa LIKE ?
                )
                ORDER BY 
                    CASE 
                        WHEN UPPER(marca) = ? THEN 1
                        WHEN UPPER(marca_limpa) LIKE ? THEN 2
                        ELSE 3
                    END ASC,
                    na_remume DESC, 
                    CASE WHEN preco = 0 THEN 999999 ELSE preco END ASC
            """
            
            param_search = f"%{termo_busca}%"
            
            df = pd.read_sql(query, conexao, params=(param_search, param_search, termo_busca, param_search))
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
                        cor_fundo = "#dcfce7" # Verde claro
                    else:
                        if preco > 0:
                            preco_str = f"R$ {preco:.2f}"
                            if preco <= p33:
                                disp_str = "Particular (Preço Baixo)"
                                cor_fundo = "#dcfce7"
                            elif preco <= p66:
                                disp_str = "Particular (Preço Intermediário)"
                                cor_fundo = "#fef9c3" # Amarelo claro
                            else:
                                disp_str = "Particular (Preço Elevado)"
                                cor_fundo = "#fee2e2" # Vermelho claro
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

# --- SEÇÃO DE LOCAIS DE RETIRADA (LEITURA DINÂMICA DO EXCEL) ---
st.markdown("---")
st.markdown("### 📍 Onde Encontrar / Locais de Atendimento")

tab_pub, tab_part = st.tabs(["🏥 Rede Pública (UBS / Distribuição)", "🛒 Farmácias Particulares"])

excel_file = "Farmacias Particular e Rede Pública.xlsx"

if os.path.exists(excel_file):
    try:
        # Carrega as abas do Excel
        df_part_excel = pd.read_excel(excel_file, sheet_name="Particular", skiprows=2)
        df_pub_excel = pd.read_excel(excel_file, sheet_name="Rede Publica", skiprows=3)

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

                nome_exibicao = f"[{nome}]({site})" if site and site.startswith("http") else nome
                link_end = f"[{end}]({link})" if link.startswith("http") else end
                
                st.markdown(f"- **{nome_exibicao}**  \n  📍 **Endereço:** {link_end}  \n  📞 **Telefone:** {tel}")

    except Exception as e:
        st.error(f"Erro ao carregar o arquivo Excel de locais: {e}")
else:
    st.info("Arquivo 'Farmacias Particular e Rede Pública.xlsx' não encontrado no diretório do projeto.")