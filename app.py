import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px

# Configuração da página e conexão com Banco de Dados SQLite
st.set_page_config(page_title="Controle 3D", layout="wide")
conn = sqlite3.connect("producao_3d.db", check_same_thread=False)
cursor = conn.cursor()

# Criar tabelas se não existirem
cursor.execute('''CREATE TABLE IF NOT EXISTS estoque 
               (id INTEGER PRIMARY KEY, marca TEXT, tipo TEXT, cor TEXT, preco REAL, metros REAL)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS producao 
               (id INTEGER PRIMARY KEY, peca TEXT, material TEXT, qtd INTEGER, tempo REAL, metros_usados REAL, custo REAL)''')
conn.commit()

st.title("🖨️ Sistema de Produção e Estoque 3D")

aba1, aba2, aba3 = st.tabs(["📋 Nova Produção", "📦 Estoque", "📊 Dashboard"])

with aba2:
    st.subheader("Cadastrar Novo Rolo de Filamento")
    with st.form("form_estoque"):
        marca = st.text_input("Marca")
        tipo = st.selectbox("Tipo", ["PLA", "ABS", "PETG", "Resina"])
        cor = st.text_input("Cor")
        preco = st.number_input("Preço do Rolo (R$)", min_value=0.0, value=120.0)
        metros = st.number_input("Metros Totais", min_value=0.0, value=330.0)
        if st.form_submit_button("Salvar no Estoque"):
            cursor.execute("INSERT INTO estoque (marca, tipo, cor, preco, metros) VALUES (?, ?, ?, ?, ?)", (marca, tipo, cor, preco, metros))
            conn.commit()
            st.success("Material adicionado!")

    st.subheader("Materiais Disponíveis")
    df_est = pd.read_sql_query("SELECT id, marca, tipo, cor, metros FROM estoque", conn)
    st.dataframe(df_est, use_container_width=True)

with aba1:
    st.subheader("Registrar Peça Produzida")
    df_est_combo = pd.read_sql_query("SELECT id, marca || ' - ' || tipo || ' (' || cor || ')' as nome, preco, metros FROM estoque WHERE metros > 0", conn)
    
    if df_est_combo.empty:
        st.warning("Cadastre um filamento na aba 'Estoque' primeiro.")
    else:
        with st.form("form_producao"):
            nome_peca = st.text_input("Nome da Peça")
            mat_selecionado = st.selectbox("Selecione o Material Utilizado", df_est_combo["nome"].tolist())
            qtd = st.number_input("Quantidade de Peças", min_value=1, value=1)
            tempo = st.number_input("Tempo por Peça (Horas)", min_value=0.1, value=2.0)
            metros_peca = st.number_input("Metros por Peça", min_value=0.1, value=10.0)
            custo_hora = st.number_input("Custo da Hora da Máquina (R$)", min_value=0.0, value=2.0)
            
            if st.form_submit_button("Calcular e Registrar Produção"):
                idx = df_est_combo["nome"].tolist().index(mat_selecionado)
                id_fil = int(df_est_combo.iloc[idx]["id"])
                preco_fil = float(df_est_combo.iloc[idx]["preco"])
                metros_totais_fil = float(df_est_combo.iloc[idx]["metros"])
                
                custo_metro = preco_fil / 330.0
                custo_material = metros_peca * custo_metro
                custo_maquina = tempo * custo_hora
                custo_total_peca = custo_material + custo_maquina
                custo_total_ordem = custo_total_peca * qtd
                total_metros_gastos = metros_peca * qtd
                
                if total_metros_gastos > metros_totais_fil:
                    st.error("Erro: Material insuficiente no estoque!")
                else:
                    cursor.execute("UPDATE estoque SET metros = metros - ? WHERE id = ?", (total_metros_gastos, id_fil))
                    cursor.execute("INSERT INTO producao (peca, material, qtd, tempo, metros_usados, custo) VALUES (?,?,?,?,?,?)",
                                   (nome_peca, mat_selecionado, qtd, tempo, total_metros_gastos, custo_total_ordem))
                    conn.commit()
                    st.success(f"Registrado! Custo unitário: R$ {custo_total_peca:.2f} | Custo Total: R$ {custo_total_ordem:.2f}")

with aba3:
    st.subheader("Indicadores de Desempenho")
    df_prod = pd.read_sql_query("SELECT * FROM producao", conn)
    if not df_prod.empty:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Custo Total Acumulado", f"R$ {df_prod['custo'].sum():.2f}")
            fig = px.bar(df_prod, x="peca", y="custo", title="Custo por Peça", labels={"peca":"Peça","custo":"Custo (R$)"})
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.metric("Total de Peças Impressas", int(df_prod['qtd'].sum()))
            fig2 = px.pie(df_prod, names="material", values="metros_usados", title="Consumo de Filamento (Metros)")
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Nenhuma produção registrada para gerar gráficos.")
