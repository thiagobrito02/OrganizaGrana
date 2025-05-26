import streamlit as st
import yaml
from yaml import SafeLoader
import pandas as pd
import matplotlib.pyplot as plt
import os

# Autenticação com Streamlit
with open("config.yaml") as file:
    config = yaml.load(file, Loader=SafeLoader)

if "usuario_autenticado" not in st.session_state:
    st.session_state.usuario_autenticado = False
    st.session_state.nome_usuario = ""

if not st.session_state.usuario_autenticado:
    st.title("🔐 Login")
    usuario_input = st.text_input("Usuário")
    senha_input = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        credenciais = config.get("usuarios", {})
        if usuario_input in credenciais and credenciais[usuario_input]["senha"] == senha_input:
            st.session_state.usuario_autenticado = True
            st.session_state.nome_usuario = credenciais[usuario_input]["nome"]
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos")
else:
    name = st.session_state.nome_usuario
    authentication_status = True

# Tema customizável
tema = st.sidebar.radio("🎨 Escolha o tema:", ["Claro", "Escuro"])
if tema == "Escuro":
    st.markdown("""
        <style>
        html, body, [class*="css"]  {
            background-color: #0e1117;
            color: #FAFAFA;
        }
        .stDataFrame thead tr th {
            background-color: #222 !important;
            color: #fff !important;
        }
        </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
        <style>
        .stDataFrame thead tr th {
            background-color: #f0f2f6 !important;
            color: #222 !important;
        }
        </style>
    """, unsafe_allow_html=True)

if st.session_state.usuario_autenticado:
    st.sidebar.success(f"Logado como {name}")

    st.title("💸 Controle de Despesas")

    CSV_FILE = "despesas.csv"

    if "despesas" not in st.session_state:
        try:
            df_carregado = pd.read_csv(CSV_FILE)
            if df_carregado.empty:
                st.session_state["despesas"] = []
            else:
                df_carregado["Data"] = pd.to_datetime(df_carregado["Data"])
                st.session_state["despesas"] = df_carregado.to_dict(orient="records")
        except (pd.errors.EmptyDataError, FileNotFoundError):
            st.session_state["despesas"] = []

    st.session_state.setdefault("reset_form", False)
    st.session_state.setdefault("form_valor", 1.0)
    st.session_state.setdefault("form_categoria", "Alimentacao")
    st.session_state.setdefault("form_data", pd.to_datetime("today"))
    st.session_state.setdefault("form_descricao", "")
    st.session_state.setdefault("form_pagamento", "Cartao")

    if st.session_state["reset_form"]:
        st.session_state.update({
            "form_valor": 1.0,
            "form_categoria": "Alimentacao",
            "form_data": pd.to_datetime("today"),
            "form_descricao": "",
            "form_pagamento": "Cartao",
            "reset_form": False
        })

    index_editando = st.session_state.get("edit_index", None)
    

    st.subheader("➕ Adicionar nova despesa" if index_editando is None else "✏️ Editar despesa")

    

    form_recorrente = st.checkbox("🔁 Despesa recorrente")
    qtd_meses = st.number_input("Quantos meses?", min_value=1, max_value=24, value=1) if form_recorrente else 1

    with st.form("form_despesa"):
        categorias = ["Alimentacao", "Mercado", "Transporte", "Lazer", "Casa", "Saude", "Pessoal", "Outros"]
        pagamentos = {"Cartao": "C", "Pix": "P", "Dinheiro": "D"}

        

        if index_editando is not None:
            despesa = st.session_state["despesas"][index_editando]
            st.session_state["form_valor"] = despesa["Valor"]
            st.session_state["form_categoria"] = despesa["Categoria"]
            st.session_state["form_data"] = pd.to_datetime(despesa["Data"])
            st.session_state["form_descricao"] = despesa["Descricao"]
            st.session_state["form_pagamento"] = despesa.get("Pagamento", "Cartao")

        valor = st.number_input("Valor (R$)", step=1.00, format="%.2f", min_value=1.00, max_value=50000.00, key="form_valor")
        categoria = st.selectbox("Categoria", categorias, key="form_categoria")
        data = st.date_input("Data", key="form_data", format="DD/MM/YYYY")
        descricao = st.text_input("Descrição", key="form_descricao")
        pagamento = st.radio("Forma de Pagamento", list(pagamentos.keys()), key="form_pagamento", horizontal=True)

        submit = st.form_submit_button("Salvar")
    if submit:
        novas_despesas = []
        for i in range(qtd_meses):
            data_iterada = (pd.to_datetime(data) + pd.DateOffset(months=i)).replace(day=1)
            novas_despesas.append({
                "Valor": valor,
                "Categoria": categoria,
                "Data": str(data_iterada),
                "Descricao": descricao,
                "Usuario": name,
                "Pagamento": pagamento
            })

        if index_editando is not None:
            st.session_state["despesas"][index_editando] = novas_despesas[0]
            del st.session_state["edit_index"]
        else:
            st.session_state["despesas"].extend(novas_despesas)

        pd.DataFrame(st.session_state["despesas"]).to_csv(CSV_FILE, index=False)
        st.session_state["reset_form"] = True
        st.rerun()

    if index_editando is not None:
        if st.button("❎ Cancelar edição"):
            del st.session_state["edit_index"]
            st.rerun()

    df = pd.DataFrame(st.session_state["despesas"])

    for col in ["Usuario", "Valor", "Categoria", "Data", "Descricao", "Pagamento"]:
        if col not in df.columns:
            df[col] = "" if col in ["Usuario", "Categoria", "Descricao", "Pagamento"] else 0.0

    if not df.empty:
        st.subheader("📋 Filtros")
        meses = sorted(df['Data'].apply(lambda x: str(x)[:7]).unique())
        filtro_mes = st.selectbox("Filtrar por mês (AAAA-MM):", ["Todos"] + meses)
        filtro_categoria = st.selectbox("Filtrar por categoria:", ["Todas"] + sorted(df["Categoria"].unique()))
        filtro_usuario = st.selectbox("Filtrar por pessoa:", ["Todos"] + sorted(df.get("Usuario", pd.Series()).unique()))

        df_filtrado = df.copy()
        if filtro_mes != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Data"].astype(str).str.startswith(filtro_mes)]
        if filtro_categoria != "Todas":
            df_filtrado = df_filtrado[df_filtrado["Categoria"] == filtro_categoria]
        if filtro_usuario != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Usuario"] == filtro_usuario]

        st.markdown("### 📄 Lista de Despesas")

        df_visivel = df_filtrado.copy().reset_index(drop=True)
        df_visivel["Data"] = pd.to_datetime(df_visivel["Data"]).dt.strftime("%d/%m/%Y")
        if "Pagamento" in df_visivel.columns:
            df_visivel["Pagamento"] = df_visivel["Pagamento"].map({"Cartao": "C", "Pix": "P", "Dinheiro": "D"})

        st.dataframe(df_visivel[["Data", "Categoria", "Valor", "Descricao", "Usuario", "Pagamento"]], use_container_width=True)

        opcoes_linha = [f"{i+1}. {row['Data']} | R$ {row['Valor']:.2f} | {row['Categoria']} | {row['Descricao']}"
                        for i, row in df_visivel.iterrows()]

        linha_idx = st.selectbox("Selecione uma despesa para editar ou remover:", options=range(len(opcoes_linha)),
                                 format_func=lambda x: opcoes_linha[x])
        idx_real = df_filtrado.index[linha_idx]

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✏️ Editar despesa selecionada"):
                st.session_state["edit_index"] = idx_real
                st.rerun()
        with col2:
            if st.button("🗑️ Remover despesa selecionada"):
                st.session_state["confirmar_exclusao"] = idx_real

        if "confirmar_exclusao" in st.session_state:
            idx_excluir = st.session_state["confirmar_exclusao"]
            with st.expander("⚠️ Confirmar remoção da despesa selecionada", expanded=True):
                st.warning("Tem certeza que deseja remover esta despesa?")
                col_a, col_b = st.columns(2)
                if col_a.button("✅ Sim, remover"):
                    st.session_state["despesas"].pop(idx_excluir)
                    pd.DataFrame(st.session_state["despesas"]).to_csv(CSV_FILE, index=False)
                    del st.session_state["confirmar_exclusao"]
                    st.rerun()
                if col_b.button("❌ Cancelar"):
                    del st.session_state["confirmar_exclusao"]
                    st.rerun()

        total_mes = df_filtrado["Valor"].sum()
        st.metric("Total acumulado no filtro", f"R$ {total_mes:.2f}")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Gráfico por Categoria**")
            cat_totais = df_filtrado.groupby("Categoria")["Valor"].sum()
            if not cat_totais.empty:
                fig1, ax1 = plt.subplots()
                ax1.pie(cat_totais, labels=cat_totais.index, autopct="%1.1f%%")
                st.pyplot(fig1)
            else:
                st.info("Sem dados para gerar o gráfico de categorias.")
        with col2:
            st.markdown("**Gráfico por Pessoa**")
            user_totais = df_filtrado.groupby("Usuario")["Valor"].sum()
            if not user_totais.empty:
                st.bar_chart(user_totais)
            else:
                st.info("Sem dados para gerar o gráfico por pessoa.")

else:
    st.error("Usuário ou senha incorretos ou não fornecidos.")
