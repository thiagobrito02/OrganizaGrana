import streamlit as st
import pandas as pd
import yaml
from yaml import SafeLoader
from datetime import datetime, date
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
import time # Para pequenos delays de teste

# 1. st.set_page_config() DEVE SER O PRIMEIRO COMANDO STREAMLIT
st.set_page_config(layout="wide", page_title="💸 Controle de Despesas")

# 2. Constantes Globais (se houver, como CATEGORIAS_PREDEFINIDAS)
CATEGORIAS_PREDEFINIDAS = ["Alimentação", "Mercado", "Transporte", "Lazer", "Casa", "Saúde", "Pessoal", "Zara", "Outros"]
PAGAMENTO_PREDEFINIDO = ["Cartão", "Pix", "Dinheiro"]

# 3. Configurações (como Google Sheets, se não dependerem de st.secrets ainda)
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDENTIALS_FILE = "organiza-grana-290b193581de.json" # Certifique-se que o caminho está correto
SHEET_NAME = "controle_despesa"

# 4. Definições de Funções (incluindo aquelas com decoradores @st.cache_resource/@st.cache_data)
@st.cache_resource
def get_google_sheets_client():
    try:
        credentials = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, SCOPE)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Erro ao conectar com Google Sheets: {e}")
        st.error("Verifique se o arquivo de credenciais JSON está correto e acessível, e se as APIs necessárias estão ativadas no Google Cloud.")
        return None # Retorna None para que o app possa lidar com a falha

# @st.cache_data(ttl=600) # Cache por 10 minutos
def get_sheet_data(_client, sheet_name_param, worksheet_name):
    if _client is None: # Se o cliente não pôde ser obtido
        return [] # Retorna uma lista vazia para evitar mais erros
    try:
        sheet = _client.open(sheet_name_param)
        worksheet = sheet.worksheet(worksheet_name)
        
        # Pega todos os valores como strings formatadas (como aparecem na planilha)
        list_of_lists = worksheet.get_values(value_render_option='FORMATTED_VALUE')
        
        if not list_of_lists or len(list_of_lists) < 1: # Verifica se a planilha não está vazia (pelo menos cabeçalho)
            st.info(f"A aba '{worksheet_name}' parece estar vazia ou sem cabeçalho.")
            return [] 
            
        headers = list_of_lists[0]
        if not headers: # Verifica se o cabeçalho não está vazio
            st.warning(f"Cabeçalho não encontrado na aba '{worksheet_name}'.")
            return []

        data_rows = list_of_lists[1:]
        
        # Converte para lista de dicionários, para manter compatibilidade com o que pd.DataFrame espera
        # e para facilitar o acesso por nome de coluna no DataFrame
        data_as_dicts = [dict(zip(headers, row)) for row in data_rows]
            
        return data_as_dicts
        
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Planilha '{sheet_name_param}' não encontrada. Verifique o nome e as permissões.")
        return []
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Aba '{worksheet_name}' não encontrada na planilha '{sheet_name_param}'.")
        return []
    except Exception as e:
        st.error(f"Erro ao buscar dados da aba '{worksheet_name}' usando get_values: {e}")
        return []
def update_worksheet_focada(_client, sheet_name_param, worksheet_name, df_to_update):
    if _client is None:
        st.error("UPDATE_WORKSHEET: Cliente Google Sheets não disponível.")
        return False # Indica falha
    try:
        st.info(f"UPDATE_WORKSHEET: Tentando ABRIR planilha '{sheet_name_param}', aba '{worksheet_name}'.")
        sheet = _client.open(sheet_name_param)
        worksheet = sheet.worksheet(worksheet_name)
        st.info(f"UPDATE_WORKSHEET: Aba '{worksheet_name}' aberta. {len(df_to_update)} linhas de dados para ATUALIZAR.")

        # Log da contagem de linhas original para contexto
        try:
            # Adiciona um pequeno delay antes de contar, para tentar pegar um estado mais estável
            time.sleep(1) 
            original_values = worksheet.get_all_values()
            original_row_count = len(original_values) if original_values else 0
            st.info(f"UPDATE_WORKSHEET: Contagem de linhas ANTES da operação: {original_row_count}")
            # if original_row_count > 0 and original_row_count <=5: # Log pequeno para ver o que estava lá
            #     st.text("Dados originais (amostra):")
            #     for r_idx, r_val in enumerate(original_values[:5]):
            #         st.text(f"  Linha GS {r_idx+1}: {r_val}")
        except Exception as e_count:
            st.warning(f"UPDATE_WORKSHEET: Não foi possível contar linhas antes: {e_count}")

        st.info(f"UPDATE_WORKSHEET: Tentando LIMPAR (worksheet.clear()) a aba '{worksheet_name}'...")
        worksheet.clear()
        st.info("UPDATE_WORKSHEET: Chamada worksheet.clear() CONCLUÍDA (sem exceção Python).")
        
        # Delay e verificação após clear
        time.sleep(2) # Delay um pouco maior
        values_after_clear = worksheet.get_all_values()
        if not values_after_clear or (len(values_after_clear) == 1 and not any(values_after_clear[0])) or len(values_after_clear) == 0 :
            st.info("DEBUG UPDATE_WORKSHEET: Aba VERIFICADA como VAZIA após clear().")
        else:
            st.warning(f"DEBUG UPDATE_WORKSHEET: Aba NÃO parece vazia após clear()! Linhas: {len(values_after_clear)}. Amostra: {values_after_clear[:2]}")


        api_response_update = None
        if not df_to_update.empty:
            st.info(f"UPDATE_WORKSHEET: Tentando ESCREVER {len(df_to_update)} linhas de dados (mais cabeçalho)...")
            data_to_write = [df_to_update.columns.values.tolist()] + df_to_update.values.tolist()
            api_response_update = worksheet.update(data_to_write, value_input_option='USER_ENTERED')
            st.info(f"UPDATE_WORKSHEET: Chamada worksheet.update() CONCLUÍDA. Resposta da API: {api_response_update}")

            if isinstance(api_response_update, dict) and api_response_update.get('updatedCells', 0) > 0:
                num_data_rows_written_api = api_response_update.get('updatedRows', 0) - 1 # -1 para cabeçalho
                if num_data_rows_written_api == len(df_to_update):
                    st.success(f"SUCESSO API: Google Sheets reportou {api_response_update.get('updatedCells')} células atualizadas em '{worksheet_name}'. {num_data_rows_written_api} linhas de dados escritas.")
                    # Verificação final adicional
                    time.sleep(2)
                    final_rows_check = worksheet.get_all_values()
                    if len(final_rows_check) == (len(df_to_update) + 1):
                        st.info("VERIFICAÇÃO FINAL: Contagem de linhas no GS corresponde ao esperado.")
                        return True
                    else:
                        st.error(f"VERIFICAÇÃO FINAL FALHOU: GS tem {len(final_rows_check)} linhas, esperado {len(df_to_update) + 1}.")
                        return False
                else:
                    st.error(f"ERRO DE ESCRITA PARCIAL API: Esperava escrever {len(df_to_update)} linhas de dados, mas API reportou {num_data_rows_written_api} (updatedRows: {api_response_update.get('updatedRows')}). Resposta: {api_response_update}")
                    return False
            else:
                st.error(f"ERRO DE ESCRITA API: Google Sheets API não confirmou células atualizadas. Resposta: {api_response_update}")
                return False
        else: # df_to_update está vazio
            # Verifica se a planilha está realmente vazia após o clear
            time.sleep(2)
            final_rows_check_empty = worksheet.get_all_values()
            if not final_rows_check_empty or (len(final_rows_check_empty) == 1 and not any(final_rows_check_empty[0])):
                st.success(f"SUCESSO: Planilha '{worksheet_name}' foi limpa (nenhum dado para escrever).")
                return True
            else:
                st.error(f"ERRO AO LIMPAR: Planilha deveria estar vazia, mas contém {len(final_rows_check_empty)} linhas.")
                return False

    except gspread.exceptions.APIError as e_api:
        st.error(f"UPDATE_WORKSHEET: ERRO DE API DO GOOGLE ao atualizar '{worksheet_name}'.")
        try:
            error_content = e_api.response.json()
            st.error("Detalhes do erro da API:")
            st.json(error_content)
        except Exception: # Fallback se .json() não funcionar ou e_api.response não existir
            st.error(f"Detalhes brutos do APIError: {e_api}")
        return False
    except Exception as e_general:
        st.error(f"UPDATE_WORKSHEET: ERRO GERAL ao atualizar '{worksheet_name}': {type(e_general).__name__} - {e_general}")
        # st.exception(e_general) # Para traceback completo se necessário
        return False

def update_worksheet(_client, sheet_name_param, worksheet_name, df_to_update):
    if _client is None:
        st.error("UPDATE_WORKSHEET: Cliente Google Sheets não disponível.")
        return False
    try:
        st.info(f"UPDATE_WORKSHEET: Abrindo planilha '{sheet_name_param}', aba '{worksheet_name}'.")
        sheet = _client.open(sheet_name_param)
        worksheet = sheet.worksheet(worksheet_name)
        
        st.info(f"UPDATE_WORKSHEET: Limpando aba '{worksheet_name}'...")
        worksheet.clear() 
        st.info("UPDATE_WORKSHEET: Chamada worksheet.clear() concluída.")

        # Pequena pausa para garantir que a limpeza seja processada pelo Google
        time.sleep(1) 

        update_result = None
        expected_rows_after_update = 0 # Se df_to_update estiver vazio (excluindo todas as despesas)
        
        if not df_to_update.empty:
            st.info(f"UPDATE_WORKSHEET: Escrevendo {len(df_to_update)} linhas de dados (mais cabeçalho)...")
            data_to_write = [df_to_update.columns.values.tolist()] + df_to_update.values.tolist()
            expected_rows_after_update = len(data_to_write) # Cabeçalho + linhas de dados
            update_result = worksheet.update(data_to_write, value_input_option='USER_ENTERED')
            st.info(f"UPDATE_WORKSHEET: Chamada worksheet.update() concluída. Resultado da API: {update_result}")
        else:
            st.info("UPDATE_WORKSHEET: df_to_update está vazio, planilha deve permanecer limpa.")
        
        # Pequena pausa e releitura para verificação final
        time.sleep(2) # Aumentar um pouco o delay antes da verificação final
        final_values_in_sheet = worksheet.get_all_values()
        num_final_rows_in_sheet = len(final_values_in_sheet) if final_values_in_sheet else 0
        # Se final_values_in_sheet for [[], [], []] (linhas vazias), len ainda será 3, mas são vazias.
        # Uma verificação mais robusta seria contar linhas com dados.
        # Para simplificar, vamos usar len por agora.
        
        # Avalia o sucesso
        if df_to_update.empty and num_final_rows_in_sheet == 0: # Se o objetivo era limpar e ficou limpa
            st.success(f"Aba '{worksheet_name}' limpa com sucesso no Google Sheets.")
            return True
        elif not df_to_update.empty and update_result and update_result.get('updatedCells', 0) > 0:
            if num_final_rows_in_sheet == expected_rows_after_update:
                st.success(f"Aba '{worksheet_name}' atualizada com sucesso no Google Sheets ({len(df_to_update)} linhas de dados).")
                return True
            else:
                st.error(f"DISCREPÂNCIA APÓS UPDATE! Esperava {expected_rows_after_update} linhas no GS, mas encontrou {num_final_rows_in_sheet}. Update result: {update_result}")
                # st.write("Dados que tentaram ser escritos:", data_to_write if not df_to_update.empty else "Nenhum (planilha deveria estar limpa)")
                # st.write("Dados finais lidos do GS:", final_values_in_sheet)
                return False
        elif df_to_update.empty and num_final_rows_in_sheet != 0: # Objetivo era limpar, mas não ficou limpa
            st.error(f"Falha ao limpar a aba '{worksheet_name}'. Encontradas {num_final_rows_in_sheet} linhas.")
            return False
        else: # update_result não indicou sucesso ou algo mais falhou
            st.error(f"Falha na operação de update da aba '{worksheet_name}'. Resultado da API (se houver): {update_result}")
            return False

    except gspread.exceptions.APIError as e_api:
        # Tenta extrair a mensagem de erro da resposta JSON da API
        error_details = e_api.args[0] if e_api.args else {}
        if isinstance(error_details, dict) and 'error' in error_details:
            error_message = error_details['error'].get('message', str(e_api))
        else:
            error_message = str(e_api)
        st.error(f"UPDATE_WORKSHEET: Erro de API do Google ao atualizar '{worksheet_name}': {error_message}")
        # st.json(error_details) # Para ver a estrutura completa do erro da API
        return False
    except Exception as e:
        st.error(f"UPDATE_WORKSHEET: Erro geral ao atualizar '{worksheet_name}': {type(e).__name__} - {e}")
        return False


# Coloque aqui suas outras definições de função:
# autenticar_usuario(), carregar_despesas(), salvar_despesas_gs(), 
# exibir_formulario_despesa(), e a exibir_tabela_despesas() que estávamos trabalhando.
# Exemplo:
# def autenticar_usuario(): ...
# def carregar_despesas(client): ... (agora recebe client)
# def salvar_despesas_gs(client, df_despesas): ... (agora recebe client e o df a salvar)
# def exibir_formulario_despesa(name): ...
# def exibir_tabela_despesas(name, client): ... (agora recebe client)


# ======================== Autenticação (exemplo, adapte) ========================
def autenticar_usuario():
    try:
        with open("config.yaml", "r", encoding="utf-8") as file: # Especificar encoding é uma boa prática
            config = yaml.load(file, Loader=SafeLoader)
    except FileNotFoundError:
        st.error("Erro Crítico: Arquivo de configuração `config.yaml` não encontrado!")
        st.info("""
            Por favor, crie o arquivo `config.yaml` no mesmo diretório do seu script `app.py` com o seguinte formato:
            
            ```yaml
            usuarios:
              seu_nome_de_usuario:
                nome: "Seu Nome de Exibição"
                senha: "sua_senha_aqui"
              outro_usuario:
                nome: "Nome do Outro Usuário"
                senha: "senha_dele"
            ```
            Substitua pelos seus dados reais.
        """)
        return None, False # Impede o resto do app de tentar rodar sem config
    except yaml.YAMLError as e:
        st.error(f"Erro Crítico: Erro ao ler o formato do arquivo `config.yaml`: {e}")
        st.info("Verifique a sintaxe YAML do seu arquivo, especialmente a indentação.")
        return None, False
    except Exception as e:
        st.error(f"Erro Crítico: Ocorreu um erro inesperado ao carregar `config.yaml`: {e}")
        return None, False

    if "usuario_autenticado" not in st.session_state:
        st.session_state.usuario_autenticado = False
        st.session_state.nome_usuario = ""

    if not st.session_state.usuario_autenticado:
        st.title("🔐 Login")

        if not config or "usuarios" not in config or not isinstance(config["usuarios"], dict):
            st.error("Erro na Configuração: A chave 'usuarios' não foi encontrada ou não está formatada corretamente em `config.yaml`.")
            st.info("Certifique-se de que `config.yaml` começa com `usuarios:` e contém os dados dos usuários indentados corretamente abaixo.")
            return None, False

        usuario_input = st.text_input("Usuário", key="login_usuario_input")
        senha_input = st.text_input("Senha", type="password", key="login_senha_input")

        if st.button("Entrar", key="login_entrar_btn"):
            user_credentials_map = config.get("usuarios", {}) # Pega o dicionário de usuários
            
            if usuario_input in user_credentials_map:
                user_config_data = user_credentials_map[usuario_input]
                
                # Verifica se user_config_data é um dicionário e contém 'senha'
                if isinstance(user_config_data, dict) and "senha" in user_config_data:
                    stored_password = user_config_data["senha"]
                    if stored_password == senha_input:
                        st.session_state.usuario_autenticado = True
                        # Usa 'nome' para exibição, ou o próprio 'usuario_input' se 'nome' não estiver definido
                        st.session_state.nome_usuario = user_config_data.get("nome", usuario_input) 
                        st.rerun()
                    else:
                        st.error("Senha incorreta.")
                else:
                    st.error(f"Configuração interna para o usuário '{usuario_input}' está malformada (falta 'senha' ou não é um dicionário). Verifique o `config.yaml`.")
            else:
                st.error(f"Usuário '{usuario_input}' não encontrado.")
        
        return None, False # Retorna se o botão não foi clicado ou se o login falhou
    else:
        # Usuário já está autenticado
        return st.session_state.nome_usuario, True

# ======================== Dados (Google Sheets) ========================
# Modifique carregar_despesas e salvar_despesas_gs para aceitar 'g_client'
g_sheets_client_global = get_google_sheets_client() # Obtém o cliente uma vez

def carregar_despesas():
    if g_sheets_client_global is None:
        st.session_state["despesas"] = []
        return

    try:
        data = get_sheet_data(g_sheets_client_global, SHEET_NAME, "Despesas")
        df = pd.DataFrame(data)

        if df.empty:
            st.session_state["despesas"] = [] # Mantém como lista vazia se não há dados
        else:
            if "Data" in df.columns:
                df["Data"] = pd.to_datetime(df["Data"], errors='coerce')
            else:
                df["Data"] = pd.NaT 
            
            # --- LÓGICA DE PARSING CORRIGIDA PARA A COLUNA "VALOR" ---
            if "Valor" in df.columns:
                valor_como_string = df["Valor"].astype(str)
            
                valor_sem_milhar = valor_como_string.str.replace(r'\.', '', regex=True)
            
                valor_com_ponto_decimal = valor_sem_milhar.str.replace(',', '.', regex=False)
                
                df["Valor"] = pd.to_numeric(valor_com_ponto_decimal, errors='coerce').fillna(0.0)
            else:
                df["Valor"] = 0.0
             
            df["Valor"] = df["Valor"].astype(float)
            
            expected_cols = ["Categoria", "Descricao", "Pagamento", "Usuario"]
            for col in expected_cols:
                if col not in df.columns:
                    df[col] = "" if col != "Usuario" else None 

            st.session_state["despesas"] = df.to_dict(orient="records")

    except Exception as e:
        st.error(f"Erro geral ao carregar e processar despesas: {e}")
        # st.exception(e) # Descomente para ver o traceback completo no Streamlit se necessário
        st.session_state["despesas"] = [] # Garante que 'despesas' seja uma lista em caso de erro

# Certifique-se que salvar_despesas_gs_atualizado() chama esta nova função:
def salvar_despesas_gs_atualizado():
    if g_sheets_client_global is None:
        st.error("SALVAR_GS: Cliente Google Sheets não inicializado.")
        return False
    if "despesas" in st.session_state:
        df_to_save = pd.DataFrame(st.session_state["despesas"])
        # ... (sua lógica para preparar df_to_save, cols_obrigatorias, conversão de data) ...
        # Exemplo da conversão de data que deve estar aqui:
        cols_obrigatorias = ["Data", "Categoria", "Valor", "Descricao", "Pagamento", "Usuario"]
        for col in cols_obrigatorias:
            if col not in df_to_save.columns:
                if col == "Data": df_to_save[col] = pd.NaT
                elif col == "Valor": df_to_save[col] = 0.0
                else: df_to_save[col] = ""
        
        if not df_to_save.empty: # Só seleciona colunas se não estiver vazio
             df_to_save = df_to_save[cols_obrigatorias]

        if "Data" in df_to_save.columns and not df_to_save.empty:
            df_to_save["Data"] = pd.to_datetime(df_to_save["Data"], errors='coerce')
            df_to_save["Data"] = df_to_save["Data"].apply(lambda x: x.strftime("%Y-%m-%d") if pd.notnull(x) else None)
        if "Valor" in df_to_save.columns and not df_to_save.empty: # Garante que valor seja numérico
            df_to_save["Valor"] = pd.to_numeric(df_to_save["Valor"], errors='coerce').fillna(0.0)


        st.info(f"SALVAR_GS: Preparando para atualizar GS. df_to_save tem {len(df_to_save)} linhas.")
        success_gs = update_worksheet_focada(g_sheets_client_global, SHEET_NAME, "Despesas", df_to_save) # Chama a nova função
        
        if success_gs:
            st.info("SALVAR_GS: update_worksheet_focada reportou SUCESSO.")
            # Se você reabilitar o cache em get_sheet_data, limpe-o aqui
            # st.cache_data.clear()
            return True
        else:
            st.warning("SALVAR_GS: update_worksheet_focada reportou FALHA.")
            return False
    st.warning("SALVAR_GS: 'despesas' não encontrado no st.session_state.")
    return False

# ======================== Funções de Interface (exibir_formulario_despesa, exibir_tabela_despesas) ========================
# Cole aqui as versões mais recentes dessas funções que estávamos depurando.
# Lembre-se de chamar salvar_despesas_gs_atualizado() onde for necessário.
# Exemplo (coloque a sua função exibir_tabela_despesas completa aqui):
def exibir_formulario_despesa(name):
    st.subheader("📝 Nova Despesa")
    with st.form("form_despesa", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            data_input = st.date_input("📅 Data", value=date.today(), format="DD/MM/YYYY", key="form_data")
        with col2:
            valor_input = st.number_input("💵 Valor (R$)", min_value=0.01, step=0.01, format="%.2f", key="form_valor")
        with col3:
            categoria_input = st.selectbox(
                "📂 Categoria", CATEGORIAS_PREDEFINIDAS, index=None,
                placeholder="Selecione uma categoria...", key="form_categoria"
            )
        descricao_input = st.text_input("📝 Descrição", key="form_descricao")
        pagamento_input = st.radio("💳 Forma de Pagamento", ["Cartão", "Pix", "Dinheiro"], horizontal=True, index=None, key="form_pagamento")
        submit_button = st.form_submit_button("➕ Adicionar")

    if submit_button:
        # Validações
        if not all([data_input, valor_input > 0, categoria_input, pagamento_input]):
            st.warning("Por favor, preencha todos os campos obrigatórios.")
            return False
        
        nova_despesa = {
            "Data": pd.to_datetime(data_input),
            "Categoria": categoria_input, "Valor": valor_input,
            "Descricao": descricao_input if descricao_input else "",
            "Pagamento": pagamento_input, "Usuario": name
        }
        # Garante que 'despesas' exista e seja uma lista
        if "despesas" not in st.session_state or not isinstance(st.session_state["despesas"], list):
            st.session_state["despesas"] = []
            
        st.session_state["despesas"].append(nova_despesa)
        salvar_despesas_gs_atualizado() # Salva no GS
        st.success("Despesa adicionada com sucesso!")
        return True
    return False

def exibir_tabela_despesas(name):
    
    # Lembre-se de usar CATEGORIAS_PREDEFINIDAS na configuração da AgGrid
    # E de chamar salvar_despesas_gs_atualizado() após edições ou remoções.
    if "despesas" not in st.session_state or not st.session_state["despesas"]:
        st.info("Nenhuma despesa registrada.")
        return

    df_despesas_orig = pd.DataFrame(st.session_state["despesas"])

    if df_despesas_orig.empty:
        st.info("Nenhuma despesa registrada.")
        return

    df_despesas_orig["Data"] = pd.to_datetime(df_despesas_orig["Data"], errors='coerce')
    df_despesas_orig["Valor"] = pd.to_numeric(df_despesas_orig["Valor"], errors='coerce').fillna(0.0)
    df_despesas_orig["Valor"] = df_despesas_orig["Valor"].astype(float) 
    df_despesas_orig["Categoria"] = df_despesas_orig["Categoria"].astype(str)

    # 1) Ordena mas mantém o índice original
    df_sorted = df_despesas_orig.sort_values(by="Data", ascending=False)
    # 2) Guarda esse índice “real” em id_original
    df_sorted["id_original"] = df_sorted.index
    # 3) Agora reseta para exibição ao usuário
    df_sorted = df_sorted.reset_index(drop=True)

    df_display = df_sorted.copy()
    df_display["Data"] = df_display["Data"].dt.strftime("%d/%m/%Y")
    
    cols_para_salvar = ["Data", "Categoria", "Valor", "Descricao", "Pagamento", "Usuario"]
    cols_display_order = ["Data", "Categoria", "Valor", "Descricao", "Pagamento", "Usuario", "id_original"]
    if not df_display.empty:
        df_display = df_display[cols_display_order]
    else: # Se df_display ficar vazio após algum processamento (improvável com as guardas)
        st.info("Não há dados para exibir na tabela após o processamento.")
        return


    gb = GridOptionsBuilder.from_dataframe(df_display)
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=15)
    
    gb.configure_default_column(
        editable=True, wrapText=False, resizable=True,
        sortable=True, filter=True, cellStyle={"fontSize": "11px"}
    )
    
    gb.configure_column("Data", header_name="📅 Data", editable=True, width=120)
    gb.configure_column(
        "Categoria", header_name="📂 Categoria", width=150,
        cellEditor='agSelectCellEditor',
        cellEditorParams={'values': CATEGORIAS_PREDEFINIDAS},
        editable=True
    )

    formatador_moeda = (
        'let valorCelula = data.Valor; '
        'if (valorCelula == null || isNaN(valorCelula)) { '
        '  return ""; '
        '} else { '
        '  let numeroFormatado = Number(valorCelula).toLocaleString("pt-BR", { '
        '    minimumFractionDigits: 2, '
        '    maximumFractionDigits: 2 '
        '  }); '
        '  return "R$ " + numeroFormatado; '
        '}'
    )
    
    gb.configure_column(
        "Valor",
        header_name="💵 Valor",
        width=200,  # Pode reajustar a largura para o formato final
        editable=True,
        cellEditor='agNumberCellEditor',
        # Adicionar 'type' pode ajudar a AgGrid a tratar a coluna internamente
        type=["numericColumn", "numberColumnFilter"],
        valueFormatter=formatador_moeda
    )

    gb.configure_column("Descricao", header_name="📝 Descrição", wrapText=True, autoHeight=True, width=250)

    gb.configure_column(
        "Pagamento", header_name="💳 Pagamento", width=100,
        cellEditor='agSelectCellEditor',
        cellEditorParams={'values': PAGAMENTO_PREDEFINIDO },
        editable=True
    )
    gb.configure_column("Usuario", header_name="👤 Usuário", editable=False, width=100)
    gb.configure_column("id_original", hide=True)

    gb.configure_selection(selection_mode="multiple", use_checkbox=True, header_checkbox=True)
    gb.configure_grid_options(domLayout="normal")

    st.subheader("📊 Tabela de Despesas")
    st.caption("Dê um duplo clique em uma célula para editar. As alterações são salvas automaticamente.")
    
    grid_response = AgGrid(
        df_display, gridOptions=gb.build(), height=500, width='100%',
        update_mode=GridUpdateMode.MODEL_CHANGED,
        data_return_mode=DataReturnMode.AS_INPUT, 
        fit_columns_on_grid_load=False, theme="alpine",
        allow_unsafe_jscode=True, 
        key="despesas_grid_ag_v5" # Chave pode ser incrementada ao mudar estrutura/formatters
    )

    data_retornada_grid = grid_response.get("data")
    houve_alteracoes = False 

    _selected_rows_data = grid_response.get("selected_rows", [])
    selected_ids_to_remove = []
    if isinstance(_selected_rows_data, list) and _selected_rows_data:
        for row_dict in _selected_rows_data:
            if row_dict and "id_original" in row_dict and row_dict["id_original"] is not None:
                selected_ids_to_remove.append(int(row_dict["id_original"]))

    if data_retornada_grid is not None:
        processed_df_for_saving = None 
        temp_df_from_grid = data_retornada_grid.copy()
        
        try:
            temp_df_from_grid["Data"] = pd.to_datetime(temp_df_from_grid["Data"], format="%d/%m/%Y", errors="coerce")
            temp_df_from_grid["Valor"] = pd.to_numeric(temp_df_from_grid["Valor"], errors='coerce').fillna(0.0)
            temp_df_from_grid["Categoria"] = temp_df_from_grid["Categoria"].astype(str)

            for col in cols_para_salvar: 
                if col not in temp_df_from_grid.columns:
                    if col == "Data": temp_df_from_grid[col] = pd.NaT
                    elif col == "Valor": temp_df_from_grid[col] = 0.0
                    else: temp_df_from_grid[col] = ""
            
            processed_df_for_saving = temp_df_from_grid[cols_para_salvar].copy()

            if processed_df_for_saving is not None and not df_sorted.empty:
                df_original_comparavel = df_sorted[cols_para_salvar].reset_index(drop=True).copy()
                df_original_comparavel["Data"] = pd.to_datetime(df_original_comparavel["Data"])
                df_original_comparavel["Valor"] = pd.to_numeric(df_original_comparavel["Valor"], errors='coerce').fillna(0.0).astype(float)
                df_original_comparavel["Categoria"] = df_original_comparavel["Categoria"].astype(str)

                df_editado_comparavel = processed_df_for_saving.reset_index(drop=True).copy()
                df_editado_comparavel["Data"] = pd.to_datetime(df_editado_comparavel["Data"]) 
                df_editado_comparavel["Valor"] = pd.to_numeric(df_editado_comparavel["Valor"], errors='coerce').fillna(0.0).astype(float)
                df_editado_comparavel["Categoria"] = df_editado_comparavel["Categoria"].astype(str)

                if not df_original_comparavel.equals(df_editado_comparavel):
                    houve_alteracoes = True
        except Exception as e:
            st.error(f"Erro ao processar dados editados da tabela: {e}")
            houve_alteracoes = False

    if houve_alteracoes:
        if processed_df_for_saving is not None:
            st.session_state["despesas"] = processed_df_for_saving.to_dict(orient='records')
            salvar_despesas_gs_atualizado() 
            st.rerun()

    _selected_rows_data = grid_response.get("selected_rows", []) 
    selected_ids_to_remove = []

    if isinstance(_selected_rows_data, pd.DataFrame):
        if not _selected_rows_data.empty:
            if "id_original" in _selected_rows_data.columns:
                selected_ids_to_remove = _selected_rows_data["id_original"].dropna().astype(int).tolist()
    elif isinstance(_selected_rows_data, list):
        if _selected_rows_data: 
            temp_ids = []
            for row_dict in _selected_rows_data:
                if row_dict and isinstance(row_dict, dict) and "id_original" in row_dict and row_dict["id_original"] is not None:
                    temp_ids.append(int(row_dict["id_original"]))
            selected_ids_to_remove = temp_ids
    
    # Dentro de exibir_tabela_despesas, no bloco do botão de remover:
    if st.button("🗑️ Remover Selecionada(s) da Planilha", disabled=not selected_ids_to_remove, key="btn_remover_despesas_v_final_teste"):
        if selected_ids_to_remove:
        
            df_temp = df_sorted.copy()
            
            try:
                df_temp.drop(index=selected_ids_to_remove, inplace=True)
            except KeyError as e:
                st.error(f"KeyError ao tentar remover linha(s) {selected_ids_to_remove}: {e}")
                st.stop()

            # Prepara para salvar (remove a coluna auxiliar)
            df_temp_to_save = df_temp.drop(columns=["id_original"], errors="ignore")
            nova_lista_despesas = df_temp_to_save.to_dict(orient="records")
            st.session_state["despesas"] = nova_lista_despesas

            gs_save_succeeded = salvar_despesas_gs_atualizado()
            if gs_save_succeeded:
                # Força recarregar da planilha na próxima execução
                if "despesas" in st.session_state:
                    del st.session_state["despesas"]
                st.success(f"{len(selected_ids_to_remove)} despesa(s) removida(s) com êxito.")
            else:
                st.error("Falha ao atualizar no Google Sheets. Verifique logs do update_worksheet.")

            st.rerun()
        else:
            st.warning("Nenhuma linha selecionada para remoção.")

# 5. Função Principal (main)
def main():
    # st.set_page_config() JÁ FOI MOVIDO PARA O TOPO DO SCRIPT

    # Ocultar "Made with Streamlit" e menu principal (opcional, mas você tinha antes)
    hide_streamlit_style = """
                <style>
                #MainMenu {visibility: hidden;}
                footer {visibility: hidden;}
                header {visibility: hidden;}
                </style>
                """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)

    nome_usuario, autenticado = autenticar_usuario()
    if not autenticado:
        st.stop() # Para a execução se não estiver autenticado

    # Carrega as despesas após a autenticação bem-sucedida e se o cliente GS estiver disponível
    if g_sheets_client_global: # Verifica se o cliente foi inicializado
        carregar_despesas()
    else:
        st.error("Cliente Google Sheets não pôde ser inicializado. Funcionalidades de dados estarão desabilitadas.")
        st.session_state["despesas"] = [] # Garante que 'despesas' exista mesmo com erro

    with st.sidebar:
        st.success(f"Logado como: {nome_usuario}")
        if st.button("🚪 Logout", key="logout_btn"):
            keys_to_clear = ["usuario_autenticado", "nome_usuario", "despesas"]
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        st.divider()
        st.title("💸 FinApp")
        aba = st.radio(
            "Navegação", 
            ["💰 Despesas", "📊 Resumo (em breve)"], 
            captions=["Lançar e ver despesas.", "Visualizar gráficos e totais."],
            key="nav_radio"
        )

    if aba == "💰 Despesas":
        st.header("Lançamento e Gestão de Despesas")
        col_form, col_spacer, col_table_actions = st.columns([0.8, 0.1, 2])
        with col_form:
            if exibir_formulario_despesa(nome_usuario):
                st.rerun() 
        with col_table_actions:
            if g_sheets_client_global: # Só exibe a tabela se o cliente GS estiver ok
                exibir_tabela_despesas(nome_usuario)
            else:
                st.warning("A tabela de despesas não pode ser exibida pois a conexão com o Google Sheets falhou.")
    
    elif aba == "📊 Resumo (em breve)":
        st.header("Resumo Financeiro")
        st.info("Funcionalidade de resumo e gráficos será implementada aqui.")

# 6. Ponto de Entrada Principal
if __name__ == "__main__":
    main()