import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px

# Configuração da página e conexão com Banco de Dados SQLite
st.set_page_config(page_title="Controle 3D", layout="wide")
conn = sqlite3.connect("", check_same_thread=False)
cursor = conn.cursor()

# Criar tabelas se não existirem (estoque agora armazena gramas)
cursor.execute('''CREATE TABLE IF NOT EXISTS estoque 
               (id INTEGER PRIMARY KEY, marca TEXT, tipo TEXT, cor TEXT, preco_por_grama REAL, gramas REAL)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS producao 
               (id INTEGER PRIMARY KEY, peca TEXT, material TEXT, qtd INTEGER, tempo REAL, gramas_usadas REAL, custo REAL)''')
conn.commit()

st.title("🖨️ Sistema de Produção e Estoque 3D (Por Gramas)")

aba1, aba2, aba3 = st.tabs(["📋 Nova Produção", "📦 Estoque", "📊 Dashboard"])

with aba2:
    st.subheader("Cadastrar / Abastecer Rolo de Filamento")
    with st.form("form_estoque"):
        # Normaliza textos para evitar duplicados por erro de digitação (ex: pla vs PLA)
        marca = st.text_input("Marca").strip().upper()
        tipo = st.selectbox("Tipo", ["PLA", "ABS", "PETG", "Resina", "Flex"])
        cor = st.text_input("Cor").strip().upper()
        preco_rolo = st.number_input("Preço pago pelo Rolo (R$)", min_value=0.0, value=120.0)
        gramas_rolo = st.number_input("Peso do Rolo em Gramas (g)", min_value=0.0, value=1000.0)
        
        if st.form_submit_button("Salvar no Estoque"):
            if marca and cor:
                preco_por_grama_novo = preco_rolo / gramas_rolo if gramas_rolo > 0 else 0
                
                # Verifica se já existe exatamente essa marca, tipo e cor no banco
                cursor.execute("SELECT id, gramas, preco_por_grama FROM estoque WHERE marca=? AND tipo=? AND cor=?", (marca, tipo, cor))
                registro_existente = cursor.fetchone()
                
                if registro_existente:
                    # Se já existe, atualiza somando as gramas e faz o preço médio ponderado
                    id_existente, gramas_atuais, preco_atual = registro_existente
                    novas_gramas_totais = gramas_atuais + gramas_rolo
                    
                    # Preço médio ponderado para não errar o custo se comprou por preços diferentes
                    novo_preco_medio = ((gramas_atuais * preco_atual) + (preco_rolo)) / novas_gramas_totais
                    
                    cursor.execute("UPDATE estoque SET gramas = ?, preco_por_grama = ? WHERE id = ?", (novas_gramas_totais, novo_preco_medio, id_existente))
                    st.success(f"Estoque atualizado! Foram adicionadas {gramas_rolo}g ao filamento existente.")
                else:
                    # Se for um filamento totalmente novo, insere uma nova linha
                    cursor.execute("INSERT INTO estoque (marca, tipo, cor, preco_por_grama, gramas) VALUES (?, ?, ?, ?, ?)", 
                                   (marca, tipo, cor, preco_por_grama_novo, gramas_rolo))
                    st.success("Novo material adicionado com sucesso!")
                conn.commit()
            else:
                st.error("Por favor, preencha a Marca e a Cor.")

    st.subheader("Materiais Disponíveis em Estoque")
    df_est = pd.read_sql_query("SELECT id, marca, tipo, cor, ROUND(gramas, 2) as 'Gramas Disponíveis' FROM estoque", conn)
    st.dataframe(df_est, use_container_width=True)

with aba1:
    st.subheader("Registrar Peça Produzida")
    df_est_combo = pd.read_sql_query("SELECT id, marca || ' - ' || tipo || ' (' || cor || ')' as nome, preco_por_grama, gramas FROM estoque WHERE gramas > 0", conn)
    
    if df_est_combo.empty:
        st.warning("Cadastre um filamento na aba 'Estoque' primeiro.")
    else:
        with st.form("form_producao"):
            nome_peca = st.text_input("Nome da Peça")
            mat_selecionado = st.selectbox("Selecione o Material Utilizado", df_est_combo["nome"].tolist())
            qtd = st.number_input("Quantidade de Peças", min_value=1, value=1)
            tempo = st.number_input("Tempo de Impressão por Peça (Horas)", min_value=0.1, value=2.0)
            gramas_peca = st.number_input("Gramas de Filamento por Peça (g)", min_value=0.1, value=30.0)
            custo_hora = st.number_input("Custo de Depreciação/Energia da Máquina por Hora (R$)", min_value=0.0, value=2.0)
            
            if st.form_submit_button("Calcular e Registrar Produção"):
                idx = df_est_combo["nome"].tolist().index(mat_selecionado)
                id_fil = int(df_est_combo.iloc[idx]["id"])
                preco_g = float(df_est_combo.iloc[idx]["preco_por_grama"])
                gramas_totais_fil = float(df_est_combo.iloc[idx]["gramas"])
                
                # Cálculos baseados em gramas
                custo_material = gramas_peca * preco_g
                custo_maquina = tempo * custo_hora
                custo_total_peca = custo_material + custo_maquina
                custo_total_ordem = custo_total_peca * qtd
                total_gramas_gastas = gramas_peca * qtd
                
                if total_gramas_gastas > gramas_totais_fil:
                    st.error(f"Erro: Estoque insuficiente! Você precisa de {total_gramas_gastas}g mas só tem {gramas_totais_fil:.1f}g.")
                else:
                    # Dá baixa nas gramas do estoque
                    cursor.execute("UPDATE estoque SET gramas = gramas - ? WHERE id = ?", (total_gramas_gastas, id_fil))
                    cursor.execute("INSERT INTO producao (peca, material, qtd, tempo, gramas_usadas, custo) VALUES (?,?,?,?,?,?)",
                                   (nome_peca, mat_selecionado, qtd, tempo, total_gramas_gastas, custo_total_ordem))
                    conn.commit()
                    st.success(f"Registrado! Custo unitário: R$ {custo_total_peca:.2f} | Custo Total da Ordem: R$ {custo_total_ordem:.2f}")

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
            fig2 = px.pie(df_prod, names="material", values="gramas_usadas", title="Consumo de Filamento (Gramas)")
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Nenhuma produção registrada para gerar gráficos.")
