import streamlit as st
import pandas as pd
import plotly.express as px
import gspread

# Configuração da página
st.set_page_config(page_title="Controle 3D", layout="wide")

# Conexão com o Google Sheets usando gspread via link público de edição
try:
    gc = gspread.public_link(st.secrets["GSHEET_URL"])
    sheet_estoque = gc.worksheet("estoque")
    sheet_producao = gc.worksheet("producao")
except Exception as e:
    st.error("Erro ao conectar com a Planilha Google. Verifique se o link nas Secrets está correto e se a planilha está compartilhada como 'Editor' para 'Qualquer pessoa com o link'.")
    st.stop()

st.title("🖨️ Sistema de Produção e Estoque 3D (Google Sheets)")

aba1, aba2, aba3 = st.tabs(["📋 Nova Produção", "📦 Estoque", "📊 Dashboard"])

# Funções auxiliares para ler dados
def ler_estoque():
    dados = sheet_estoque.get_all_values()
    if not dados:
        return pd.DataFrame(columns=["ID", "Marca", "Tipo", "Cor", "Preco_Por_Grama", "Gramas"])
    return pd.DataFrame(dados[1:], columns=dados[0])

def ler_producao():
    dados = sheet_producao.get_all_values()
    if not dados:
        return pd.DataFrame(columns=["ID", "Peca", "Material", "Qtd", "Tempo", "Gramas_Usadas", "Custo"])
    return pd.DataFrame(dados[1:], columns=dados[0])

with aba2:
    st.subheader("Cadastrar / Abastecer Rolo de Filamento")
    with st.form("form_estoque"):
        marca = st.text_input("Marca").strip().upper()
        tipo = st.selectbox("Tipo", ["PLA", "ABS", "PETG", "Resina", "Flex"])
        cor = st.text_input("Cor").strip().upper()
        preco_rolo = st.number_input("Preço pago pelo Rolo (R$)", min_value=0.0, value=120.0)
        gramas_rolo = st.number_input("Peso do Rolo em Gramas (g)", min_value=0.0, value=1000.0)
        
        if st.form_submit_button("Salvar no Estoque"):
            if marca and cor:
                preco_por_grama_novo = preco_rolo / gramas_rolo if gramas_rolo > 0 else 0
                df_est = ler_estoque()
                
                # Se a planilha estiver vazia, cria o cabeçalho
                if df_est.empty:
                    sheet_estoque.append_row(["ID", "Marca", "Tipo", "Cor", "Preco_Por_Grama", "Gramas"])
                    df_est = ler_estoque()

                # Verifica duplicado
                filtro = (df_est["Marca"] == marca) & (df_est["Tipo"] == tipo) & (df_est["Cor"] == cor)
                
                if not df_est.empty and filtro.any():
                    idx_linha = df_est[filtro].index[0] + 2 # +2 por causa do cabeçalho e índice 0
                    gramas_atuais = float(df_est.loc[df_est[filtro].index[0], "Gramas"])
                    preco_atual = float(df_est.loc[df_est[filtro].index[0], "Preco_Por_Grama"])
                    
                    novas_gramas_totais = gramas_atuais + gramas_rolo
                    novo_preco_medio = ((gramas_atuais * preco_atual) + preco_rolo) / novas_gramas_totais
                    
                    sheet_estoque.update_cell(idx_linha, 5, str(novo_preco_medio))
                    sheet_estoque.update_cell(idx_linha, 6, str(novas_gramas_totais))
                    st.success(f"Estoque atualizado! Adicionadas {gramas_rolo}g ao filamento existente.")
                else:
                    novo_id = len(df_est) + 1
                    sheet_estoque.append_row([str(novo_id), marca, tipo, cor, str(preco_por_grama_novo), str(gramas_rolo)])
                    st.success("Novo material salvo com sucesso!")
            else:
                st.error("Preencha a Marca e a Cor.")

    st.subheader("Materiais Disponíveis em Estoque")
    df_visualizar_est = ler_estoque()
    if not df_visualizar_est.empty:
        st.dataframe(df_visualizar_est, use_container_width=True)

with aba1:
    st.subheader("Registrar Peça Produzida")
    df_combo = ler_estoque()
    
    if df_combo.empty:
        st.warning("Cadastre um filamento na aba 'Estoque' primeiro.")
    else:
        df_combo["Gramas"] = df_combo["Gramas"].astype(float)
        df_disponivel = df_combo[df_combo["Gramas"] > 0]
        opcoes = [f"{r['Marca']} - {r['Tipo']} ({r['Cor']})" for _, r in df_disponivel.iterrows()]
        
        if not opcoes:
            st.warning("Não há materiais com estoque disponível.")
        else:
            with st.form("form_producao"):
                nome_peca = st.text_input("Nome da Peça")
                mat_selecionado = st.selectbox("Selecione o Material Utilizado", opcoes)
                qtd = st.number_input("Quantidade de Peças", min_value=1, value=1)
                tempo = st.number_input("Tempo de Impressão por Peça (Horas)", min_value=0.1, value=2.0)
                gramas_peca = st.number_input("Gramas de Filamento por Peça (g)", min_value=0.1, value=30.0)
                custo_hora = st.number_input("Custo da Máquina por Hora (R$)", min_value=0.0, value=2.0)
                
                if st.form_submit_button("Calcular e Registrar Produção"):
                    idx = opcoes.index(mat_selecionado)
                    item_sel = df_disponivel.iloc[idx]
                    
                    custo_material = gramas_peca * float(item_sel["Preco_Por_Grama"])
                    custo_maquina = tempo * custo_hora
                    custo_total_peca = custo_material + custo_maquina
                    custo_total_ordem = custo_total_peca * qtd
                    total_gramas_gastas = gramas_peca * qtd
                    
                    if total_gramas_gastas > float(item_sel["Gramas"]):
                        st.error(f"Estoque insuficiente! Precisa de {total_gramas_gastas}g e tem {item_sel['Gramas']}g.")
                    else:
                        # Atualiza estoque na planilha
                        idx_linha_est = int(item_sel.name) + 2
                        novas_gramas = float(item_sel["Gramas"]) - total_gramas_gastas
                        sheet_estoque.update_cell(idx_linha_est, 6, str(novas_gramas))
                        
                        # Salva produção
                        df_prod_atual = ler_producao()
                        if df_prod_atual.empty:
                            sheet_producao.append_row(["ID", "Peca", "Material", "Qtd", "Tempo", "Gramas_Usadas", "Custo"])
                            df_prod_atual = ler_producao()
                        
                        novo_id_prod = len(df_prod_atual) + 1
                        sheet_producao.append_row([str(novo_id_prod), nome_peca, mat_selecionado, str(qtd), str(tempo), str(total_gramas_gastas), str(custo_total_ordem)])
                        st.success(f"Registrado com sucesso! Custo Total: R$ {custo_total_ordem:.2f}")

with aba3:
    st.subheader("Indicadores de Desempenho")
    df_prod_grafico = ler_producao()
    if not df_prod_grafico.empty and len(df_prod_grafico) > 0:
        df_prod_grafico["Custo"] = df_prod_grafico["Custo"].astype(float)
        df_prod_grafico["Qtd"] = df_prod_grafico["Qtd"].astype(int)
        df_prod_grafico["Gramas_Usadas"] = df_prod_grafico["Gramas_Usadas"].astype(float)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Custo Total Acumulado", f"R$ {df_prod_grafico['Custo'].sum():.2f}")
            fig = px.bar(df_prod_grafico, x="Peca", y="Custo", title="Custo por Peça")
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.metric("Total de Peças Impressas", int(df_prod_grafico['Qtd'].sum()))
            fig2 = px.pie(df_prod_grafico, names="Material", values="Gramas_Usadas", title="Consumo de Filamento (g)")
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Nenhuma produção registrada para gerar gráficos.")
