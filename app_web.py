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
            
            # Busca todos os medicamentos equivalentes (pela substância limpa)
            query = """
                SELECT substancia, marca, apresentacao, laboratorio, preco, na_remume, substancia_limpa, marca_limpa
                FROM produtos 
                WHERE substancia_limpa IN (
                    SELECT DISTINCT substancia_limpa 
                    FROM produtos 
                    WHERE substancia_limpa LIKE ? OR marca_limpa LIKE ?
                )
            """
            
            param_search = f"%{termo_busca}%"
            df = pd.read_sql(query, conexao, params=(param_search, param_search))
            conexao.close()

            if df.empty:
                st.info("Nenhum medicamento encontrado com esse termo.")
            else:
                # Função de ordenação por relevância do nome (prefixo exato primeiro)
                def prioridade_nome(row):
                    s_name = str(row['substancia']).upper()
                    m_name = str(row['marca']).upper()
                    if s_name.startswith(termo_busca) or m_name.startswith(termo_busca):
                        return 1
                    elif termo_busca in s_name or termo_busca in m_name:
                        return 2
                    return 3

                df['relevancia'] = df.apply(prioridade_nome, axis=1)

                # --- SELEÇÃO INTELIGENTE DA REDE PÚBLICA (REMUME = 1) ---
                df_pub_full = df[df['na_remume'] == 1].sort_values(by=['relevancia', 'apresentacao', 'substancia'])
                
                if not df_pub_full.empty:
                    # 1. Pega primeiro uma linha para CADA APRESENTAÇÃO DIFERENTE disponível
                    df_pub_unicas = df_pub_full.drop_duplicates(subset=['apresentacao'], keep='first')
                    
                    # 2. Se as apresentações únicas já forem até 8, usa elas. Se forem mais de 8, pega as 8 primeiras únicas.
                    if len(df_pub_unicas) >= 8:
                        df_pub = df_pub_unicas.head(8)
                    else:
                        # Se houver menos de 8 apresentações únicas (ex: 3 apresentações), preenche as vagas restantes (até completar 8) com outras opções
                        sobra_vagas = 8 - len(df_pub_unicas)
                        df_resto = df_pub_full.loc[~df_pub_full.index.isin(df_pub_unicas.index)].head(sobra_vagas)
                        df_pub = pd.concat([df_pub_unicas, df_resto], ignore_index=True)
                else:
                    df_pub = pd.DataFrame()

                # --- REDE PARTICULAR (REMUME = 0) ---
                df_part = df[df['na_remume'] == 0].copy()
                df_part['preco_ordem'] = df_part['preco'].apply(lambda x: 999999 if x == 0 else x)
                df_part = df_part.sort_values(by=['relevancia', 'preco_ordem'])

                # Unifica a lista final (Rede Pública diversificada no topo + Particulares abaixo)
                df_final = pd.concat([df_pub, df_part], ignore_index=True)

                # Cálculo dos quartis de preços para coloração
                precos_validos = df_part[df_part['preco'] > 0]['preco']
                p33 = precos_validos.quantile(0.33) if not precos_validos.empty else 0
                p66 = precos_validos.quantile(0.66) if not precos_validos.empty else 0

                resultados_formatados = []
                cores_linhas = []

                for _, row in df_final.iterrows():
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