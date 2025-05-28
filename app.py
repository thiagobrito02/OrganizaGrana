import streamlit as st
import yaml
from yaml import SafeLoader
import pandas as pd
import plotly.express as px


# ======================== Autenticação ========================
def autenticar_usuario():
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
        return None, False
    else:
        return st.session_state.nome_usuario, True


# ======================== Tema ========================
import streamlit as st
import yaml
from yaml import SafeLoader
import pandas as pd
import matplotlib.pyplot as plt


# ======================== Autenticação ========================
def autenticar_usuario():
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
        return None, False
    else:
        return st.session_state.nome_usuario, True


# ======================== Dados (CSV) ========================
def carregar_despesas(csv_file="despesas.csv"):
    if "despesas" not in st.session_state:
        try:
            df_carregado = pd.read_csv(csv_file)
            if df_carregado.empty:
                st.session_state["despesas"] = []
            else:
                df_carregado["Data"] = pd.to_datetime(df_carregado["Data"])
                st.session_state["despesas"] = df_carregado.to_dict(orient="records")
        except (pd.errors.EmptyDataError, FileNotFoundError):
            st.session_state["despesas"] = []


def salvar_despesas(csv_file="despesas.csv"):
    if "despesas" in st.session_state:
        df_para_salvar = pd.DataFrame(st.session_state["despesas"])
        df_para_salvar.to_csv(csv_file, index=False)

# ======================== Formulário de Despesas ========================
def exibir_formulario_despesa(name, csv_file="despesas.csv"):
    index_editando = st.session_state.get("edit_index", None)

    st.subheader("➕ Adicionar nova despesa" if index_editando is None else "✏️ Editar despesa")

    form_recorrente = st.checkbox("🔁 Despesa recorrente")
    qtd_meses = st.number_input("Quantos meses?", min_value=1, max_value=24, value=1) if form_recorrente else 1

    categorias = ["Alimentacao", "Mercado", "Transporte", "Lazer", "Casa", "Saude", "Pessoal", "Outros"]
    pagamentos = {"Cartao": "C", "Pix": "P", "Dinheiro": "D"}

    # Preenche os campos se for edição
    if index_editando is not None and "form_populado" not in st.session_state:
        despesa = st.session_state["despesas"][index_editando]
        st.session_state["form_valor"] = despesa["Valor"]
        st.session_state["form_categoria"] = despesa["Categoria"]
        st.session_state["form_data"] = pd.to_datetime(despesa["Data"])
        st.session_state["form_descricao"] = str(despesa["Descricao"]) if pd.notnull(despesa["Descricao"]) else ""
        st.session_state["form_pagamento"] = despesa.get("Pagamento", "Cartao")
        st.session_state["form_populado"] = True


    with st.form("form_despesa"):
        valor = st.number_input("Valor (R$)", step=1.00, format="%.2f", min_value=1.00, max_value=50000.00, key="form_valor")
        categoria = st.selectbox("Categoria", categorias, key="form_categoria")
        data = st.date_input("Data", key="form_data", format="DD/MM/YYYY")
        descricao = st.text_input("Descrição", key="form_descricao")
        pagamento = st.radio("Forma de Pagamento", list(pagamentos.keys()), key="form_pagamento", horizontal=True)
        submit = st.form_submit_button("Salvar")

    if submit:
        novas_despesas = []
        for i in range(qtd_meses):
            data_iterada = pd.to_datetime(data) + pd.DateOffset(months=i)
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
            del st.session_state["form_populado"]
        else:
            st.session_state["despesas"].extend(novas_despesas)

        salvar_despesas(csv_file)
        st.rerun()

    if index_editando is not None:
        if st.button("❎ Cancelar edição"):
            del st.session_state["edit_index"]
            if "form_populado" in st.session_state:
                del st.session_state["form_populado"]
            st.rerun()


# ======================== Tabela, Gráficos e Análises ========================
def exibir_tabela_despesas(name, csv_file="despesas.csv"):
    df = pd.DataFrame(st.session_state["despesas"])

    if df.empty:
        st.info("Nenhuma despesa registrada.")
        return

    df["Data"] = pd.to_datetime(df["Data"])
    df["Usuario"] = df["Usuario"].astype(str)

    for col in ["Usuario", "Valor", "Categoria", "Data", "Descricao", "Pagamento"]:
        if col not in df.columns:
            df[col] = "" if col in ["Usuario", "Categoria", "Descricao", "Pagamento"] else 0.0

    meses_disponiveis = sorted(df['Data'].dt.strftime("%Y-%m").unique())
    filtro_mes_default = pd.to_datetime("today").strftime("%Y-%m") if pd.to_datetime("today").strftime("%Y-%m") in meses_disponiveis else "Todos"
    usuarios_disponiveis = sorted(df["Usuario"].unique())
    filtro_usuario_default = name if name in usuarios_disponiveis else "Todos"

    st.subheader("📋 Filtros")
    filtro_mes = st.selectbox("Filtrar por mês (AAAA-MM):", ["Todos"] + meses_disponiveis, index=(["Todos"] + meses_disponiveis).index(filtro_mes_default) if filtro_mes_default in (["Todos"] + meses_disponiveis) else 0)
    filtro_categoria = st.selectbox("Filtrar por categoria:", ["Todas"] + sorted(df["Categoria"].unique()))
    filtro_usuario = st.selectbox("Filtrar por pessoa:", ["Todos"] + usuarios_disponiveis, index=(["Todos"] + usuarios_disponiveis).index(filtro_usuario_default) if filtro_usuario_default in (["Todos"] + usuarios_disponiveis) else 0)

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
    df_visivel["Pagamento"] = df_visivel["Pagamento"].map({"Cartao": "💳 Cartão", "Pix": "⚡ Pix", "Dinheiro": "💵 Dinheiro"})

    emoji_categoria = {
        "Alimentacao": "🍽️",
        "Mercado": "🛒",
        "Transporte": "🚗",
        "Lazer": "🎉",
        "Casa": "🏠",
        "Saude": "🩺",
        "Pessoal": "👤",
        "Outros": "📦"
    }
    df_visivel["Categoria"] = df_visivel["Categoria"].map(lambda c: f"{emoji_categoria.get(c, '')} {c}")
    df_visivel["Valor"] = df_visivel["Valor"].apply(lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    colunas_renomeadas = {
        "Data": "📅 Data",
        "Categoria": "📂 Categoria",
        "Valor": "💰 Valor",
        "Descricao": "📝 Descrição",
        "Usuario": "👤 Pessoa",
        "Pagamento": "💳 Pagamento"
    }
    df_visivel.rename(columns=colunas_renomeadas, inplace=True)
    st.dataframe(df_visivel, use_container_width=True, hide_index=True)
    
    opcoes_linha = [f"{i+1}. {row['📅 Data']} | {row['💰 Valor']} | {row['📂 Categoria']} | {row['📝 Descrição']}" for i, row in df_visivel.iterrows()]
    linha_idx = st.selectbox("Selecione uma despesa para editar ou remover:", options=range(len(opcoes_linha)), format_func=lambda x: opcoes_linha[x])
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
        st.warning("Tem certeza que deseja remover esta despesa?")
        col_a, col_b = st.columns(2)
        if col_a.button("✅ Sim, remover", key="confirm_remove_button"):
            st.session_state["despesas"].pop(idx_excluir)
            salvar_despesas(csv_file)
            del st.session_state["confirmar_exclusao"]
            st.rerun()
        if col_b.button("❌ Cancelar", key="cancel_remove_button"):
            del st.session_state["confirmar_exclusao"]
            st.rerun()

    total_mes = df_filtrado["Valor"].sum()
    st.metric("Total acumulado no filtro", f"R$ {total_mes:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    st.markdown("**Análise percentual por categoria**")
    cat_totais = df_filtrado.groupby("Categoria")["Valor"].sum()
    if not cat_totais.empty:
        total_geral = cat_totais.sum()
        for cat, val in cat_totais.items():
            perc = (val / total_geral) * 100
            st.write(f"{cat}: R$ {val:.2f} ({perc:.1f}%)")

    # # === Gráfico por Categoria ===
    # st.markdown("**📊 Distribuição por Categoria**")
    # cat_totais = df_filtrado.groupby("Categoria")["Valor"].sum()
    # if not cat_totais.empty:
    #     fig1, ax1 = plt.subplots()
    #     ax1.pie(cat_totais, labels=cat_totais.index, autopct="%1.1f%%", startangle=90)
    #     ax1.axis("equal")
    #     st.pyplot(fig1)
    # else:
    #     st.info("Sem dados suficientes para gráfico de categoria.")

    # # === Gráfico por Pessoa ===
    # st.markdown("**👥 Gastos por Pessoa**")
    # user_totais = df_filtrado.groupby("Usuario")["Valor"].sum()
    # if not user_totais.empty:
    #     fig2, ax2 = plt.subplots()
    #     user_totais.plot(kind="bar", ax=ax2, color="#66b3ff")
    #     ax2.set_ylabel("Valor (R$)")
    #     ax2.set_xlabel("Usuário")
    #     ax2.set_title("Gasto por Pessoa")
    #     st.pyplot(fig2)
    # else:
    #     st.info("Sem dados para gráfico de pessoa.")

    # # === Top categorias por valor acumulado ===
    # st.markdown("**🏆 Top Categorias por Valor Acumulado**")
    # top_categorias = df_filtrado.groupby("Categoria")["Valor"].sum().sort_values(ascending=False).head(5)
    # if not top_categorias.empty:
    #     fig3, ax3 = plt.subplots()
    #     bars = ax3.barh(top_categorias.index, top_categorias.values, color="#ffcc99")
    #     ax3.set_xlabel("Valor Total (R$)")
    #     ax3.set_title("Top Categorias de Despesa")
    #     ax3.invert_yaxis()

    #     for bar in bars:
    #         width = bar.get_width()
    #         ax3.text(width + 1, bar.get_y() + bar.get_height()/2, f"R$ {width:,.2f}", va='center')

    #     st.pyplot(fig3)
    # else:
    #     st.info("Sem categorias suficientes para o ranking.")

    # # === Comparativo mês a mês ===
    # st.markdown("**📆 Comparativo Mês a Mês**")
    # df_filtrado["AnoMes"] = df_filtrado["Data"].dt.to_period("M").astype(str)
    # gastos_mensais = df_filtrado.groupby("AnoMes")["Valor"].sum()
    # if not gastos_mensais.empty:
    #     fig4, ax4 = plt.subplots()
    #     gastos_mensais.plot(kind="bar", ax=ax4, color="#90ee90")
    #     ax4.set_ylabel("Valor (R$)")
    #     ax4.set_title("Evolução dos Gastos por Mês")
    #     st.pyplot(fig4)
    # else:
    #     st.info("Sem dados para comparativo mensal.")

    # === Gráfico por Categoria ===
    st.markdown("**📊 Distribuição por Categoria**")
    cat_totais = df_filtrado.groupby("Categoria")["Valor"].sum().reset_index()
    if not cat_totais.empty:
        fig1 = px.pie(cat_totais, names="Categoria", values="Valor", title="Distribuição por Categoria", hole=0.3)
        fig1.update_traces(textinfo='percent+label')
        fig1.update_layout(showlegend=True)
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.info("Sem dados suficientes para gráfico de categoria.")

    # === Gráfico por Pessoa ===
    st.markdown("**👥 Gastos por Pessoa**")
    user_totais = df_filtrado.groupby("Usuario")["Valor"].sum().reset_index()
    if not user_totais.empty:
        fig2 = px.bar(user_totais, x="Usuario", y="Valor", title="Gasto por Pessoa", text_auto=True)
        fig2.update_layout(xaxis_title="Pessoa", yaxis_title="Valor (R$)")
        fig2.update_traces(marker_color="#6a9cfc")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Sem dados para gráfico de pessoa.")

    # === Top categorias por valor acumulado ===
    st.markdown("**🏆 Top Categorias por Valor Acumulado**")
    top_categorias = df_filtrado.groupby("Categoria")["Valor"].sum().sort_values(ascending=False).head(5).reset_index()
    if not top_categorias.empty:
        fig3 = px.bar(top_categorias, x="Valor", y="Categoria", orientation="h", title="Top Categorias de Despesa",
                      text="Valor", color_discrete_sequence=["#ffcc99"])
        fig3.update_layout(yaxis=dict(categoryorder='total ascending'), xaxis_title="Valor (R$)")
        fig3.update_traces(texttemplate='R$ %{text:.2f}', textposition='outside')
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("Sem categorias suficientes para o ranking.")

    # === Comparativo mês a mês ===
    st.markdown("**📆 Comparativo Mês a Mês**")
    df_filtrado["AnoMes"] = df_filtrado["Data"].dt.to_period("M").astype(str)
    gastos_mensais = df_filtrado.groupby("AnoMes")["Valor"].sum().reset_index()
    if not gastos_mensais.empty:
        fig4 = px.bar(gastos_mensais, x="AnoMes", y="Valor", title="Evolução dos Gastos por Mês", text_auto=True)
        fig4.update_layout(xaxis_title="Mês", yaxis_title="Valor (R$)", xaxis_tickangle=-45)
        fig4.update_traces(marker_color="#99d98c")
        st.plotly_chart(fig4, use_container_width=True)
    else:
        st.info("Sem dados para comparativo mensal.")


# ======================== Execução Principal ========================
def main():
    CSV_FILE = "despesas.csv"
    name, authentication_status = autenticar_usuario()

    if not authentication_status:
        st.stop()

    carregar_despesas(CSV_FILE)

    st.sidebar.success(f"Logado como {name}")
    if st.sidebar.button("🚪 Logout"):
        st.session_state.clear()
        st.rerun()

    st.title("💸 Controle de Despesas")

    if exibir_formulario_despesa(name, CSV_FILE):
        st.rerun()

    exibir_tabela_despesas(name, CSV_FILE)


if __name__ == "__main__":
    main()
