# ======================== IMPORTS ========================
import streamlit as st
import pandas as pd
import yaml
from yaml import SafeLoader
from datetime import datetime, date
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
from st_aggrid.shared import JsCode
import time
import locale
from pandas.api.types import is_numeric_dtype
import numpy as np # Importe a biblioteca numpy
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from dateutil.relativedelta import relativedelta # Importe no início do seu arquivo

# ======================== CONFIGURAÇÕES GERAIS ========================
st.set_page_config(
    layout="wide",
    page_title="💸 FinApp - Controle de Despesas",
    initial_sidebar_state="collapsed",
)


# ======================== CSS ========================
CUSTOM_CSS = """
<style>
.css-1v0mbdj.e115fcil1 { max-width: 400px; margin: auto; }
section[data-testid="stTextInput"] > div,
section[data-testid="stPassword"] > div {
    max-width: 300px;
    margin: auto;
}
.stButton > button {
    display: block;
    margin: 1rem auto;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ======================== CONSTANTES ========================
CATEGORIAS_PREDEFINIDAS = ["Alimentação", "Mercado", "Transporte", "Lazer", "Casa", "Saúde", "Pessoal", "Zara", "Outros"]
PAGAMENTO_PREDEFINIDO = ["Cartão", "Pix", "Dinheiro"]
TAGS_POR_CATEGORIA = {
    "Alimentação": ["Restaurante", "iFood/Delivery", "Lanche", "Padaria"],
    "Mercado": ["Supermercado", "Hortifruti", "Açougue"],
    "Transporte": ["Combustível", "Uber/99", "Manutenção", "Avião", "Seguro", "IPVA", "Estacionamento", "Parcelamento"],
    "Lazer": ["Passeios", "Cinema", "Shows", "Viagens"],
    "Casa": ["Aluguel", "Luz", "Água", "Internet", "Condomínio", "Diarista", "Manutenção", "Decoração", "Impostos", "Outros"],
    "Saúde": ["Academia", "Farmácia", "Consulta", "Plano de Saúde", "Exames", "Tratamentos", "Remédios", "Dentista", "Suplementos"],
    "Pessoal": ["Roupas", "Calçados", "Cosméticos", "Cabelo", "Pensão", "Presentes", "Educação", "Giovanna", "Outros"],
    "Zara": ["Petshop", "Veterinário", "Ração", "Brinquedos"],
    "Outros": ["Presentes", "Taxas", "Investimentos","Assinaturas"] }
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDENTIALS_FILE = "organiza-grana-290b193581de.json"
SHEET_NAME = "controle_despesa"
WORKSHEET_NAME = "Despesas"

# ======================== GOOGLE SHEETS ========================
@st.cache_resource
def get_sheets_client():
    try:
        # Pega as credenciais diretamente do st.secrets
        creds_dict = st.secrets["google_credentials"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        client = gspread.authorize(creds)
        
        # Testa a conexão para garantir que as permissões estão corretas
        client.open(SHEET_NAME)
        
        return client
    except Exception as e:
        # Se qualquer passo acima falhar, mostra um erro claro em vez de entrar em loop
        st.error(f"Falha ao conectar com o Google Sheets: {e}")
        st.warning("Verifique se as credenciais 'google_credentials' nos Segredos estão corretas e se a conta de serviço tem permissão para acessar a planilha.")
        return None # Retorna None para indicar a falha na conexão

@st.cache_data(ttl=300, show_spinner=False)
def read_sheet_data(_client, sheet_name, worksheet_name):
    worksheet = _client.open(sheet_name).worksheet(worksheet_name)
    values = worksheet.get_values(value_render_option="FORMATTED_VALUE")
    if len(values) < 2:
        return pd.DataFrame()
    df = pd.DataFrame(values[1:], columns=values[0])
    if "id_original" not in df.columns:
        df["id_original"] = list(range(len(df)))
    df["id_original"] = pd.to_numeric(df["id_original"], errors="coerce").fillna(-1).astype(int)
    return df

def write_sheet_data(client, sheet_name, worksheet_name, df):
    if df.empty:
        # Se o dataframe estiver vazio após a exclusão, limpamos a planilha e deixamos só o cabeçalho.
        # Isso pode ser ajustado se o comportamento desejado for outro.
        try:
            worksheet = client.open(sheet_name).worksheet(worksheet_name)
            worksheet.clear()
            # Se quiser manter o cabeçalho mesmo com a planilha vazia:
            # worksheet.update([df.columns.tolist()], value_input_option="USER_ENTERED")
            return True
        except Exception as e:
            st.error(f"Erro ao limpar a planilha: {e}")
            return False

    try:
        worksheet = client.open(sheet_name).worksheet(worksheet_name)
        # Manter o backup é uma boa prática caso a escrita falhe.
        backup = worksheet.get_all_values()
        try:
            # --- ESTA É A CORREÇÃO PRINCIPAL ---
            # 1. Limpa completamente a planilha antes de escrever os novos dados.
            worksheet.clear()
            
            # 2. Prepara os dados (cabeçalho + linhas) e os escreve na planilha agora vazia.
            data = [df.columns.tolist()] + df.astype(str).values.tolist()
            worksheet.update(data, value_input_option="USER_ENTERED")
            return True
        except Exception as e:
            # Se a escrita falhar, tenta restaurar o backup.
            st.error(f"Erro ao salvar dados. Restaurando backup... Erro: {e}")
            worksheet.clear() # Limpa qualquer escrita parcial.
            worksheet.update(backup) # Escreve os dados do backup de volta.
            return False
    except Exception as e:
        st.error(f"Erro geral ao interagir com o Google Sheets: {e}")
        return False

# ======================== UTILS ========================

def format_currency_brl(value):
    """Formata um número para o padrão de moeda brasileiro (R$ 1.234,56)"""
    if not isinstance(value, (int, float)):
        return "R$ 0,00"
    # Formata o número com separador de milhar (,) e 2 casas decimais (.)
    # Ex: 1234.56 -> "1,234.56"
    valor_formatado = f"{value:,.2f}"
    # Troca os separadores para o padrão brasileiro
    # "1,234.56" -> "1.234,56"
    valor_formatado_br = valor_formatado.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {valor_formatado_br}"

def safe_parse_value(value):
    """Converte de forma segura um valor que pode ser um texto em pt-BR para float."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return 0.0
    if isinstance(value, (int, float)):
        return round(value, 2)
    if isinstance(value, str):
        if not value.strip():
            return 0.0
        try:
            # Substitui o ponto de milhar por nada e a vírgula de decimal por ponto
            clean_str = value.replace('.', '').replace(',', '.')
            return round(float(clean_str), 2)
        except (ValueError, TypeError):
            return 0.0
    return 0.0

def are_dataframes_equal(df1, df2):
    # Se os dataframes não tiverem o mesmo formato, são diferentes
    if df1.shape != df2.shape or list(df1.columns) != list(df2.columns):
        return False
    
    # Compara os dataframes usando o método nativo do pandas, que é mais seguro
    return df1.equals(df2)

def on_category_change():
    """
    Callback para ser executado quando a categoria muda.
    Reseta a seleção da tag para 'Nenhuma' para evitar estados inválidos.
    """
    # Acessamos a chave do seletor de tag e a definimos como 'Nenhuma'
    # Isso garante que ao trocar de categoria, o campo de tag seja reiniciado.
    st.session_state.form_tag = "Nenhuma"

# ======================== AUTENTICAÇÃO ========================
def authenticate_user():
    # Pega os usuários diretamente do st.secrets
    try:
        users = st.secrets["usuarios"]
    except Exception as e:
        st.error("Erro Crítico: Não foi possível carregar a configuração de usuários a partir dos Segredos do Streamlit.")
        st.info("Verifique se a seção [usuarios] foi configurada corretamente nos Segredos do seu aplicativo.")
        return None, False

    # Inicializa o estado de autenticação se não existir
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    # Se o usuário não estiver autenticado, mostra a tela de login
    if not st.session_state.authenticated:
        
        # --- ESTRUTURA DE LAYOUT PARA CENTRALIZAR O LOGIN ---
        # Cria 3 colunas, usaremos a do meio para o conteúdo
        _, col_central, _ = st.columns([1, 1.5, 1])

        with col_central:
            # --- CONTAINER PARA O "CARTÃO DE LOGIN" ---
            # O border=True cria uma caixa visualmente separada
            with st.container(border=True):
                
                # Opcional: Adicione sua logo aqui
                # st.image("caminho/para/sua/logo.png", width=150)
                
                st.markdown("<h2 style='text-align: center;'>Bem-vindo ao FinApp</h2>", unsafe_allow_html=True)
                
                # Formulário de login
                with st.form("login_form"):
                    st.text_input("Usuário", key="user_input")
                    st.text_input("Senha", type="password", key="password_input")
                    
                    # Botão de submit que ocupa a largura toda do container
                    submitted = st.form_submit_button("Entrar", use_container_width=True)

                    if submitted:
                        # Adiciona um spinner para dar feedback visual durante a verificação
                        with st.spinner("Verificando credenciais..."):
                            user = st.session_state.user_input
                            pw = st.session_state.password_input

                            if user in users and users[user]["senha"] == pw:
                                st.session_state.authenticated = True
                                st.session_state.user_display = users[user]["nome"]
                                # Limpa os campos de input do estado da sessão
                                del st.session_state.user_input
                                del st.session_state.password_input
                                st.rerun()
                            else:
                                st.error("Usuário ou senha incorretos.")
        
        # Se chegou até aqui, não está autenticado
        return None, False

    # Se já passou do "if" acima, significa que está autenticado
    return st.session_state.user_display, True

# ======================== FUNÇÕES PRINCIPAIS ========================
def load_expenses():
    client = get_sheets_client()
    
    # Se a conexão falhou, o client será None.
    if client is None:
        # Para o app não quebrar, criamos um DataFrame vazio e paramos a execução aqui.
        st.session_state["expenses_df"] = pd.DataFrame(columns=["Data", "Categoria", "Valor", "Descricao", "Pagamento", "Usuario", "id_original"])
        return

    df = read_sheet_data(client, SHEET_NAME, WORKSHEET_NAME)
    if df.empty:
        df = pd.DataFrame(columns=["Data", "Categoria", "Valor", "Descricao", "Pagamento", "Usuario", "id_original"])
    else:
        if "Valor" in df.columns:
            df["Valor"] = df["Valor"].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            df["Valor"] = pd.to_numeric(df["Valor"], errors='coerce').fillna(0).round(2)
        
        if "Data" in df.columns:
            df["Data"] = pd.to_datetime(df["Data"], errors="coerce")

    st.session_state["expenses_df"] = df


def save_expenses():
    client = get_sheets_client()
    df = st.session_state.get("expenses_df", pd.DataFrame()).copy()
    if df.empty or len(df) < 1:
        st.warning("Nenhuma despesa para salvar ou DataFrame inconsistente.")
        return False
    # ✅ Garante que a coluna "Data" está no formato datetime
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    df["Data"] = df["Data"].dt.strftime("%Y-%m-%d")
    df["Valor"] = df["Valor"].apply(lambda x: f"{x:.2f}".replace(".", ","))
    return write_sheet_data(client, SHEET_NAME, WORKSHEET_NAME, df)


def get_next_id():
    df = st.session_state.get("expenses_df", pd.DataFrame())
    return int(df["id_original"].max()) + 1 if not df.empty else 0

from dateutil.relativedelta import relativedelta

def render_new_expense_form(user_display):
    st.subheader("Adicionar Nova Despesa")

    # --- PASSO 1: BLOCO INICIAL COM DESTAQUE ---
    # Usamos um container com borda para dar destaque visual
    with st.container(border=True):
        st.markdown("##### ❶ Comece por aqui")
        
        # Cria a lista de categorias com uma opção inicial "em branco"
        categorias_opcoes = ["Selecione uma categoria..."] + CATEGORIAS_PREDEFINIDAS
        
        # Inicializa o estado do seletor na primeira execução
        if "form_categoria" not in st.session_state:
            st.session_state.form_categoria = categorias_opcoes[0]

        # O seletor de categoria que controla a exibição do resto do formulário
        st.selectbox(
            "Categoria da Despesa", 
            options=categorias_opcoes,
            key="form_categoria"
        )
        
        st.checkbox(
            "É uma despesa recorrente?", 
            key="recorrente_checkbox", 
            value=st.session_state.get("recorrente_checkbox", False)
        )
    # --- FIM DO BLOCO INICIAL ---

    # --- PASSO 2: FORMULÁRIO CONDICIONAL ---
    # O formulário completo só aparece se uma categoria válida for selecionada
    if st.session_state.form_categoria != "Selecione uma categoria...":
        
        with st.form("new_expense_details"): # Nome do form alterado para evitar conflitos
            st.markdown(f"##### ❷ Detalhes para **{st.session_state.form_categoria}**")

            # O seletor de Tag continua dinâmico como antes
            opcoes_tag = ["Nenhuma"] + TAGS_POR_CATEGORIA.get(st.session_state.form_categoria, [])
            tag_selecionada = st.selectbox("Tag (Opcional)", options=opcoes_tag, key="form_tag")

            descricao = st.text_input("Descrição")
            
            col_valor, col_data = st.columns(2)
            with col_valor:
                valor = st.number_input("Valor (R$)", min_value=0.01, step=0.01, format="%.2f")
            with col_data:
                data = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")

            pagamento = st.radio("Pagamento", PAGAMENTO_PREDEFINIDO, horizontal=True)

            quantidade_parcelas = 1
            if st.session_state.get("recorrente_checkbox"):
                quantidade_parcelas = st.number_input(
                    "Número de parcelas", min_value=2, max_value=60, value=2, step=1, key="quantidade_parcelas"
                )

            submitted = st.form_submit_button("Adicionar Despesa", use_container_width=True)

            if submitted:
                # Ao submeter, buscamos a categoria do estado da sessão
                categoria_final = st.session_state.get("form_categoria")
                is_recorrente = st.session_state.get("recorrente_checkbox", False)
                
                if is_recorrente:
                    num_parcelas = st.session_state.get("quantidade_parcelas", 2)
                else:
                    num_parcelas = 1

                # Lógica de criação das despesas (continua a mesma)
                despesas_para_adicionar = []
                proximo_id = get_next_id()
                for i in range(num_parcelas):
                    # ... (resto da sua lógica para popular nova_despesa) ...
                    nova_despesa = {
                        "Data": pd.to_datetime(data + relativedelta(months=i)), "Categoria": categoria_final,
                        "Tag": tag_selecionada if tag_selecionada != "Nenhuma" else "",
                        "Valor": valor, "Descricao": f"{descricao} ({i+1}/{num_parcelas})" if is_recorrente and num_parcelas > 1 else descricao,
                        "Pagamento": pagamento, "Usuario": user_display, "id_original": proximo_id + i
                    }
                    despesas_para_adicionar.append(nova_despesa)
                    
                novas_despesas_df = pd.DataFrame(despesas_para_adicionar)
                st.session_state["expenses_df"] = pd.concat([st.session_state["expenses_df"], novas_despesas_df], ignore_index=True)
                st.session_state.submission_success = True

                if save_expenses():
                    st.success(f"{num_parcelas} despesa(s) adicionada(s) com sucesso!")
                    read_sheet_data.clear()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Erro ao salvar despesa.")

def render_expense_table(df_para_exibir):
    
    if df_para_exibir.empty:
        st.info("Nenhuma despesa para exibir com os filtros atuais.")
        return

    # --- Usando o GridOptionsBuilder de forma explícita e completa ---
    gb = GridOptionsBuilder.from_dataframe(df_para_exibir)

    # 1. HABILITA A PAGINAÇÃO
    # Define o tamanho da página e ativa a funcionalidade.
    gb.configure_pagination(paginationPageSize=20, paginationAutoPageSize=False)

    # 2. HABILITA A SELEÇÃO COM CHECKBOXES
    # Essencial para a função de exclusão.
    gb.configure_selection(
        selection_mode="multiple",
        use_checkbox=True,
        header_checkbox=True
    )
    
    # 1. VALUE GETTER: Prepara o valor para a CÉLULA DE EDIÇÃO.
    # Pega o número (ex: 200.5) e formata como texto com vírgula (ex: "200,50").
    js_value_getter = JsCode("""
        function(params) {
            if (params.data && typeof params.data.Valor === 'number') {
                return params.data.Valor.toFixed(2).replace('.', ',');
            }
            return params.data.Valor;
        }
    """)

    # 2. VALUE FORMATTER: Formata o valor para a CÉLULA DE VISUALIZAÇÃO.
    # Adiciona o "R$" para quando a célula não está sendo editada.
    js_value_formatter = JsCode("""
        function(params) {
            if (typeof params.value === 'number') {
                return 'R$ ' + params.value.toFixed(2).replace('.', ',');
            }
            return params.value;
        }
    """)

    # 3. VALUE PARSER: "Entende" o que o usuário digita na edição.
    # Pega o texto (ex: "200,50") e converte de volta para um número (ex: 200.5).
    js_value_parser = JsCode("""
        function(params) {
            let value = params.newValue;
            if (value === null || value === undefined || value === '') { return 0; }
            let clean_string = String(value).replace(/\./g, '').replace(',', '.');
            let number = parseFloat(clean_string);
            return isNaN(number) ? params.oldValue : number;
        }
    """)
    
    gb.configure_column("Valor", editable=True, valueGetter=js_value_getter, valueParser=js_value_parser, valueFormatter=js_value_formatter, type=["numericColumn", "numberColumnFilter"])
    gb.configure_column("Data", type=["dateColumnFilter", "customDateTimeFormat"], custom_format_string='dd/MM/yyyy', editable=True)
    gb.configure_column("Categoria", editable=True, cellEditor='agSelectCellEditor', cellEditorParams={'values': CATEGORIAS_PREDEFINIDAS})
    gb.configure_column("Tag", headerName="Tag", editable=True)
    gb.configure_column("Pagamento", editable=True, cellEditor='agSelectCellEditor', cellEditorParams={'values': PAGAMENTO_PREDEFINIDO})
    gb.configure_column("Descricao", editable=True, autoHeight=True, wrapText=True) # wrapText e autoHeight para descrições longas
    gb.configure_column("Usuario", editable=False)
    gb.configure_column("id_original", hide=True)

    # Constrói o dicionário final de opções
    grid_options = gb.build()
    # --- FIM DA CONFIGURAÇÃO ---

    # --- Formulário Único para Edição, Salvamento e Exclusão ---
    with st.form("main_form"):
        st.subheader("Tabela de Despesas")
        st.caption("Você pode editar as células diretamente. Ao final, clique em Salvar ou Excluir.")


        # --- CHAMADA DO AGGRID MINIMALISTA ---
        grid_return = AgGrid(
            df_para_exibir,
            gridOptions=grid_options,
            key='stable_expense_grid',
            
            # PARÂMETROS ESSENCIAIS (mantidos)
            update_mode=GridUpdateMode.MODEL_CHANGED,
            data_return_mode=DataReturnMode.AS_INPUT,
            allow_unsafe_jscode=True,
            enable_enterprise_modules=False,
            reload_data=True,

            # PARÂMETROS REMOVIDOS PARA O TESTE
            # height=600, 
            # theme='alpine',
            # fit_columns_on_grid_load=True
        )
        # --- FIM DA CHAMADA ---

        # Botões de ação dentro do mesmo formulário
        col1, col2, _ = st.columns([1, 1, 3])
        with col1:
            save_pressed = st.form_submit_button("✔️ Salvar Alterações")
        with col2:
            delete_pressed = st.form_submit_button("❌ Excluir Selecionadas")


    # --- Lógica de Ação (só roda quando um dos botões do formulário é clicado) ---

    if save_pressed:
        updated_df = grid_return['data'].copy()
        updated_df['Valor'] = updated_df['Valor'].apply(safe_parse_value)
        updated_df["Data"] = pd.to_datetime(updated_df["Data"], errors="coerce")
        
        # Aqui, precisamos mesclar as mudanças de volta no dataframe principal
        # que está no session_state antes de salvar, para não perder os dados não filtrados.
        df_completo = st.session_state['expenses_df'].copy()
        updated_df.set_index('id_original', inplace=True)
        df_completo.set_index('id_original', inplace=True)
        df_completo.update(updated_df)
        df_completo.reset_index(inplace=True)

        df_completo['Data'] = pd.to_datetime(df_completo['Data'], errors='coerce')


        st.session_state['expenses_df'] = df_completo
        
        if save_expenses():
            st.success("Alterações salvas com sucesso!")
            read_sheet_data.clear()
            time.sleep(1)
            st.rerun()
        else:
            st.error("Erro ao salvar alterações.")

    if delete_pressed:
        selected_rows = grid_return['selected_rows']
        if not selected_rows:
            st.warning("Nenhuma linha selecionada para exclusão.")
            return

        ids_para_excluir = [row['id_original'] for row in selected_rows]
        
        df_completo = st.session_state['expenses_df'].copy()
        df_apos_exclusao = df_completo.query("id_original not in @ids_para_excluir")
        
        st.session_state["expenses_df"] = df_apos_exclusao
        if save_expenses():
            st.success("Despesas excluídas com sucesso!")
            read_sheet_data.clear()
            time.sleep(1)
            st.rerun()
        else:
            st.error("Erro ao excluir despesas.")

# ======================== FILTROS ========================

from datetime import datetime

from datetime import datetime

def setup_filtros(df, usuario_logado):
    st.sidebar.header("Filtros")

    # --- Listas de Opções ---
    anos_disponiveis = ["Todos"] + sorted(df['Data'].dt.year.unique(), reverse=True)
    meses_nomes = ["Todos", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    
    lista_usuarios = sorted(df['Usuario'].unique().tolist())
    if usuario_logado not in lista_usuarios:
        lista_usuarios.insert(0, usuario_logado)
    usuarios_disponiveis = ["Todos"] + lista_usuarios

    # --- Inicialização do Estado ---
    if 'filtro_ano' not in st.session_state: st.session_state.filtro_ano = datetime.now().year
    if 'filtro_mes' not in st.session_state: st.session_state.filtro_mes = meses_nomes[datetime.now().month]
    if 'filtro_usuario' not in st.session_state: st.session_state.filtro_usuario = usuario_logado
    if 'filtro_categorias' not in st.session_state: st.session_state.filtro_categorias = ["Todas"]

    # --- Widgets ---
    ano = st.sidebar.selectbox("Ano", anos_disponiveis, key="filtro_ano")
    mes_nome = st.sidebar.selectbox("Mês", meses_nomes, key="filtro_mes")
    usuario = st.sidebar.selectbox("Usuário", usuarios_disponiveis, key="filtro_usuario")
    
    categorias_disponiveis = ["Todas"] + sorted(df['Categoria'].unique().tolist())
    categorias = st.sidebar.multiselect("Categorias", categorias_disponiveis, key="filtro_categorias")

    # --- Retorna as seleções ---
    meses_map = {nome: i for i, nome in enumerate(meses_nomes)}
    mes_num = meses_map[mes_nome]
    
    return ano, mes_num, usuario, categorias

# ======================== GRÁFICOS ========================
def render_dashboard(df):
    st.subheader("Dashboard de Despesas")

    # 1. Métricas Principais (KPIs)
    total_gasto = df['Valor'].sum()
    media_por_transacao = df['Valor'].mean()
    categoria_mais_cara = df.groupby('Categoria')['Valor'].sum().idxmax()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Gasto", f"R$ {total_gasto:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    col2.metric("Média por Transação", f"R$ {media_por_transacao:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    col3.metric("Categoria Principal", categoria_mais_cara)
    
    st.markdown("---")

    # 2. Gráficos
    col_graf1, col_graf2 = st.columns(2)

    with col_graf1:
        st.subheader("Gastos por Categoria")
        gastos_por_categoria = df.groupby('Categoria')['Valor'].sum().sort_values(ascending=False)
        fig_cat = px.bar(
            gastos_por_categoria,
            x=gastos_por_categoria.index,
            y=gastos_por_categoria.values,
            title="Total Gasto por Categoria",
            labels={'x': 'Categoria', 'y': 'Valor Gasto (R$)'},
            template="plotly_white"
        )
        st.plotly_chart(fig_cat, use_container_width=True)

    with col_graf2:
        st.subheader("Evolução dos Gastos")
        # Certifique-se que a coluna 'Data' é do tipo datetime
        df['Data'] = pd.to_datetime(df['Data'])
        gastos_por_dia = df.groupby(df['Data'].dt.date)['Valor'].sum()
        fig_dia = px.line(
            x=gastos_por_dia.index,
            y=gastos_por_dia.values,
            title="Gastos por Dia",
            labels={'x': 'Data', 'y': 'Valor Gasto (R$)'},
            markers=True
        )
        fig_dia.update_layout(template="plotly_white")
        st.plotly_chart(fig_dia, use_container_width=True)

# ======================== DASHBOARD ANÁLISE MENSAL ========================
meses_nomes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
               "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
import plotly.graph_objects as go
from dateutil.relativedelta import relativedelta

def render_dashboard_analise_mensal(df_usuario_filtrado, ano, mes):
    # O título agora reflete o usuário selecionado na barra lateral, lendo do session_state
    usuario_selecionado = st.session_state.get("filtro_usuario", "Todos")
    st.header(f"Análise de {meses_nomes[mes-1]}/{ano} para: {usuario_selecionado}")

    # A função agora opera diretamente no DataFrame que recebe (df_usuario_filtrado),
    # que já foi filtrado por usuário na função main.
    # O seletor de usuário que existia aqui foi REMOVIDO por ser redundante.

    # Lógica de filtro de data para pegar o mês atual e o anterior
    data_inicio_mes_atual = datetime(ano, mes, 1)
    data_fim_mes_atual = data_inicio_mes_atual + relativedelta(months=1) - relativedelta(days=1)
    data_inicio_mes_anterior = data_inicio_mes_atual - relativedelta(months=1)

    df_mes_atual = df_usuario_filtrado[
        (df_usuario_filtrado['Data'] >= pd.to_datetime(data_inicio_mes_atual)) & 
        (df_usuario_filtrado['Data'] <= pd.to_datetime(data_fim_mes_atual))
    ]
    df_mes_anterior = df_usuario_filtrado[
        (df_usuario_filtrado['Data'] >= pd.to_datetime(data_inicio_mes_anterior)) & 
        (df_usuario_filtrado['Data'] < pd.to_datetime(data_inicio_mes_atual))
    ]

    # KPIs são calculados. Se não houver dados, a soma será 0.
    total_atual = df_mes_atual['Valor'].sum()
    total_anterior = df_mes_anterior['Valor'].sum()
    delta = ((total_atual - total_anterior) / total_anterior * 100) if total_anterior > 0 else 0

    col1, col2 = st.columns(2)
    col1.metric(f"Total Gasto em {meses_nomes[mes-1]}", format_currency_brl(total_atual))
    col2.metric("Total Gasto no Mês Anterior", format_currency_brl(total_anterior), f"{delta:,.2f}%")

    st.markdown("---")
    
    # Se não houver absolutamente nenhuma despesa para o usuário no mês selecionado,
    # mostramos um aviso e não tentamos desenhar os gráficos.
    if df_mes_atual.empty:
        st.info(f"Nenhuma despesa encontrada para '{usuario_selecionado}' no período selecionado.")
        return

    # Os gráficos são desenhados normalmente com os dados do mês atual
    col_graf1, col_graf2 = st.columns(2)
    with col_graf1:
        st.subheader("Comparativo por Categoria")
        gastos_cat_atual = df_mes_atual.groupby('Categoria')['Valor'].sum()
        gastos_cat_anterior = df_mes_anterior.groupby('Categoria')['Valor'].sum()
        df_comp = pd.DataFrame({'Mês Atual': gastos_cat_atual, 'Mês Anterior': gastos_cat_anterior}).fillna(0)
        
        fig = go.Figure(data=[
            go.Bar(name='Mês Anterior', x=df_comp.index, y=df_comp['Mês Anterior']),
            go.Bar(name='Mês Atual', x=df_comp.index, y=df_comp['Mês Atual'])
        ])
        fig.update_layout(barmode='group', template="plotly_white", title_text="Categoria vs. Categoria")
        st.plotly_chart(fig, use_container_width=True)

    with col_graf2:
        st.subheader("Composição dos Gastos")
        # Usando o Sunburst que implementamos
        df_para_sunburst = df_mes_atual.copy()
        df_para_sunburst['Tag'] = df_para_sunburst['Tag'].fillna('Sem Tag').replace('', 'Sem Tag')
        fig_sunburst = px.sunburst(
            df_para_sunburst,
            path=['Categoria', 'Tag'],
            values='Valor',
            title=f"Composição dos Gastos em {meses_nomes[mes-1]}"
        )
        fig_sunburst.update_traces(textinfo="label+percent entry")
        st.plotly_chart(fig_sunburst, use_container_width=True)

# ======================== DASHBOARD TENDÊNCIAS ========================
def render_dashboard_tendencias(df): # A função agora recebe o DF já filtrado
    st.header("Análise de Tendências")
    st.info("Este gráfico reflete o período selecionado nos filtros da barra lateral.")

    # A função não filtra mais por 'últimos 12 meses'. Ela usa o que recebe.
    df_para_analise = df.copy()

    if df_para_analise.empty:
        st.warning("Nenhum dado encontrado para o período e filtros selecionados.")
        return

    # O resto da lógica de agrupamento e plotagem continua a mesma
    df_para_analise['AnoMes'] = df_para_analise['Data'].dt.to_period('M')
    gastos_mensais = df_para_analise.groupby('AnoMes')['Valor'].sum().sort_index()
    gastos_mensais.index = gastos_mensais.index.to_timestamp()

    fig = px.line(
        x=gastos_mensais.index, y=gastos_mensais.values,
        title="Evolução Mensal do Gasto Total",
        labels={'x': 'Mês', 'y': 'Valor Gasto (R$)'}, markers=True
    )
    fig.update_layout(template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    st.subheader("Análise Detalhada por Categoria e Tag")
    col_filtro1, col_filtro2 = st.columns(2)
    with col_filtro1:
        categorias_unicas = sorted(df_para_analise['Categoria'].unique())
        categorias_selecionadas = st.multiselect("Selecione as categorias:", categorias_unicas, default=categorias_unicas[:3])

    with col_filtro2:
        if categorias_selecionadas:
            tags_disponiveis = sorted(df_para_analise[df_para_analise['Categoria'].isin(categorias_selecionadas)]['Tag'].fillna('Sem Tag').unique())
            tags_selecionadas = st.multiselect("Selecione as tags:", tags_disponiveis, default=tags_disponiveis)
        else:
            tags_selecionadas = []

    if categorias_selecionadas and tags_selecionadas:
        df_filtrado_cat = df_para_analise[
            (df_para_analise['Categoria'].isin(categorias_selecionadas)) &
            (df_para_analise['Tag'].isin(tags_selecionadas))
        ]
        df_filtrado_cat['Legenda'] = df_filtrado_cat['Categoria'] + ' - ' + df_filtrado_cat['Tag'].fillna('Sem Tag')
        gastos_mensais_cat = df_filtrado_cat.groupby(['AnoMes', 'Legenda'])['Valor'].sum().unstack(fill_value=0).sort_index()
        gastos_mensais_cat.index = gastos_mensais_cat.index.to_timestamp()

        fig2 = px.line(
            gastos_mensais_cat, x=gastos_mensais_cat.index, y=gastos_mensais_cat.columns,
            title="Evolução Mensal por Seleção",
            labels={'x': 'Mês', 'value': 'Valor Gasto (R$)', 'variable': 'Seleção'}, markers=True
        )
        fig2.update_layout(template="plotly_white")
        st.plotly_chart(fig2, use_container_width=True)

# ======================== DASHBOARD VISÃO DETALHADA ========================
def render_dashboard_deep_dive(df):
    st.header("Visão Detalhada dos Gastos")

    col1, col2 = st.columns([1, 1])

    with col1:
        # 1. Treemap
        st.subheader("Composição por Categoria e Tag (Treemap)")
        gastos_categoria = df.groupby('Categoria')['Valor'].sum().reset_index()

        # Garante que a coluna Tag não tenha valores nulos que quebrem o gráfico
        df_para_treemap = df.copy()
        df_para_treemap['Tag'] = df_para_treemap['Tag'].fillna('Sem Tag')
        df_para_treemap.loc[df_para_treemap['Tag'] == '', 'Tag'] = 'Sem Tag'

        # O 'path' agora é hierárquico: Categoria -> Tag
        fig = px.treemap(
            df_para_treemap, 
            path=['Categoria', 'Tag'], 
            values='Valor',
            title='Área proporcional ao gasto por Categoria e Tag',
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig.update_traces(root_color="lightgrey")
        fig.update_layout(margin = dict(t=50, l=25, r=25, b=25))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
            st.subheader("Top 10 Maiores Despesas")
            # A lógica para obter o top 10 continua a mesma
            top_10 = df.sort_values('Valor', ascending=False).head(10)

            # 1. Cria uma cópia do DataFrame para formatação de exibição.
            top_10_para_exibir = top_10.copy()

            # 2. Formata a coluna de Data para o padrão dd/mm/yyyy.
            top_10_para_exibir['Data'] = top_10_para_exibir['Data'].dt.strftime('%d/%m/%Y')
            
            # 3. Formata a coluna de Valor para o padrão de moeda brasileira.
            #    Isso funciona porque já definimos o locale para pt_BR no início do script.
            top_10_para_exibir['Valor'] = top_10_para_exibir['Valor'].apply(format_currency_brl)
            
            # 4. Exibe o DataFrame já formatado, sem precisar do column_config.
            st.dataframe(
                top_10_para_exibir[['Data', 'Categoria','Descricao', 'Valor']],
                use_container_width=True,
                hide_index=True
            )

    st.markdown("---")

    # 3. Gráfico de Barras Empilhadas
    st.subheader("Forma de Pagamento por Categoria")
    gastos_pagamento = df.groupby(['Categoria', 'Pagamento'])['Valor'].sum().unstack(fill_value=0)
    fig2 = px.bar(
        gastos_pagamento, x=gastos_pagamento.index, y=gastos_pagamento.columns,
        title="Como você paga por cada categoria?",
        labels={'x': 'Categoria', 'value': 'Valor Gasto (R$)', 'variable': 'Forma de Pagamento'},
        template="plotly_white"
    )
    st.plotly_chart(fig2, use_container_width=True)

#from io import StringIO

# ======================== MAIN ========================
def main():
    # --- BLOCO 1: RESET DO FORMULÁRIO (Executado primeiro após um envio) ---
    if st.session_state.get("submission_success", False):
        st.session_state.submission_success = False
        st.session_state.recorrente_checkbox = False
        st.session_state.form_categoria = "Selecione uma categoria..."
        st.rerun()

    # --- BLOCO 2: AUTENTICAÇÃO DO USUÁRIO ---
    user_display, is_auth = authenticate_user()
    if not is_auth:
        return

    # --- BLOCO 3: CARREGAMENTO E PREPARAÇÃO DOS DADOS ---
    if "expenses_df" not in st.session_state:
        load_expenses()
    
    df_completo = st.session_state.get("expenses_df", pd.DataFrame())

    # Garante que a coluna 'Data' seja sempre do tipo datetime antes de qualquer operação
    if not df_completo.empty and 'Data' in df_completo.columns:
        df_completo['Data'] = pd.to_datetime(df_completo['Data'], errors='coerce')

    # --- BLOCO 4: FILTROS E PREPARAÇÃO DA SIDEBAR ---
    # A função setup_filtros agora apenas mostra os widgets e retorna as escolhas do usuário
    ano_selecionado, mes_selecionado_num, usuario_selecionado, categorias_selecionadas = setup_filtros(df_completo, user_display)

    st.sidebar.title("FinApp")
    st.sidebar.markdown(f"Bem-vindo, {user_display}")
    if st.sidebar.button("Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    # --- BLOCO 5: LÓGICA DE FILTRAGEM CENTRALIZADA ---
    # Primeiro, filtra pelo usuário. Este será o nosso dataframe base para os dashboards de longo prazo.
    df_base_usuario_filtrado = df_completo.copy()
    if usuario_selecionado != "Todos":
        df_base_usuario_filtrado = df_base_usuario_filtrado[df_base_usuario_filtrado['Usuario'] == usuario_selecionado]

    # Em seguida, cria um segundo DataFrame com TODOS os filtros aplicados, para as visões detalhadas.
    df_filtrado_final = df_base_usuario_filtrado.copy()
    if ano_selecionado != "Todos":
        df_filtrado_final = df_filtrado_final[df_filtrado_final['Data'].dt.year == ano_selecionado]
    if mes_selecionado_num != 0: # 0 = "Todos"
        df_filtrado_final = df_filtrado_final[df_filtrado_final['Data'].dt.month == mes_selecionado_num]
    if "Todas" not in categorias_selecionadas:
        df_filtrado_final = df_filtrado_final[df_filtrado_final['Categoria'].isin(categorias_selecionadas)]
            
    # --- BLOCO 6: RENDERIZAÇÃO DA PÁGINA PRINCIPAL ---
    st.title("💰 Controle de Despesas")

    tab_dashboard, tab_lancamentos = st.tabs(["📊 Dashboards", "✍️ Lançamentos"])

    with tab_dashboard:
        st.header("Análise Visual de Gastos")

        # Lógica para mostrar/esconder o dashboard de Análise Mensal
        opcoes_dashboard = ["Análise de Tendências", "Visão Detalhada"]
        if ano_selecionado != "Todos" and mes_selecionado_num != 0:
            opcoes_dashboard.insert(0, "Análise Mensal")
        
        dashboard_selecionado = st.selectbox(
            "Escolha uma visão de análise:",
            opcoes_dashboard
        )
        
        # Chamadas corretas para cada dashboard com o DataFrame apropriado
        if dashboard_selecionado == "Análise Mensal":
            render_dashboard_analise_mensal(df_base_usuario_filtrado, ano_selecionado, mes_selecionado_num)
        elif dashboard_selecionado == "Análise de Tendências":
            render_dashboard_tendencias(df_base_usuario_filtrado)
        elif dashboard_selecionado == "Visão Detalhada":
            render_dashboard_deep_dive(df_filtrado_final)

    with tab_lancamentos:
        st.header("Gerenciar Despesas")
        
        tab_adicionar, tab_tabela = st.tabs(["Adicionar Nova Despesa", "Ver Tabela Detalhada"])

        with tab_adicionar:
            render_new_expense_form(user_display)
        with tab_tabela:
            render_expense_table(df_filtrado_final)

if __name__ == "__main__":
    main()
