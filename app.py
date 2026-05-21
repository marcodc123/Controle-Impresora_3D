import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client

# Configuração da página
st.set_page_config(page_title="Controle 3D", layout="wide")

# Conexão segura com o Banco de Dados Permanente (Supabase)
# O Streamlit vai puxar os dados das "Secrets" que vamos configurar no próximo passo
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.title("🖨️ Sistema de Produção e Estoque 3D (Dados Salvos)")

aba1, aba2, aba3 = st.tabs(["📋 Nova Produção", "📦 Estoque", "📊 Dashboard"])

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
                
                # Busca no Supabase se já existe material igual
                resposta = supabase.table("estoque").select("*").eq("marca", marca).eq("tipo", tipo).eq("cor", cor).execute()
                registro_existente = resposta.data
                
                if registro_existente:
                    id_existente = registro_existente[0]["id"]
                    gramas_atuais = float(registro_existente[0]["gramas"])
                    preco_atual = float(registro_existente[0]["preco_por_grama"])
                    
                    novas_gramas_totais = gramas_atuais + gramas_rolo
                    novo_preco_medio = ((gramas_atuais * preco_atual) + (preco_rolo)) / novas_gramas_totais
                    
                    supabase.table("estoque").update({"gramas": novas_gramas_totais, "preco_por_grama": novo_preco_medio}).eq("id", id_existente).execute()
                    st.success(f"Estoque atualizado de forma permanente! Adicionadas {gramas_rolo}g.")
                else:
                    supabase.table("estoque").insert({"marca": marca, "tipo": tipo, "cor": cor, "preco_por_grama": preco_por_grama_novo, "gramas": gramas_rolo}).execute()
                    st.success("Novo material salvo de forma permanente!")
            else:
                st.error("Por favor, preencha a Marca e a Cor.")

    st.subheader("Materiais Disponíveis em Estoque")
    dados_est = supabase.table("estoque").select("id, marca, tipo, cor, gramas").execute().data
    if dados_est:
        df_est = pd.DataFrame(dados_est)
        df_est.columns = ["ID", "Marca", "Tipo", "Cor", "Gramas Disponíveis"]
        st.dataframe(df_est, use_container_width=True)
    else:
        st.info("Nenhum material em estoque.")

with aba1:
    st.subheader("Registrar Peça Produzida")
    dados_combo = supabase.table("estoque").select("id, marca, tipo, cor, preco_por_grama, gramas").gt("gramas", 0).execute().data
    
    if not dados_combo:
        st.warning("Cadastre um filamento na aba 'Estoque' primeiro.")
    else:
        # Monta a lista visual de seleção
        opcoes = [f"{item['marca']} - {item['tipo']} ({item['cor']})" for item in dados_combo]
        
        with st.form("form_producao"):
            nome_peca = st.text_input("Nome da Peça")
            mat_selecionado = st.selectbox("Selecione o Material Utilizado", opciones)
            qtd = st.number_input("Quantidade de Peças", min_value=1, value=1)
            tempo = st.number_input("Tempo de Impressão por Peça (Horas)", min_value=0.1, value=2.0)
            gramas_peca = st.number_input("Gramas de Filamento por Peça (g)", min_value=0.1, value=30.0)
            custo_hora = st.number_input("Custo de Depreciação/Energia por Hora (R$)", min_value=0.0, value=2.0)
            
            if st.form_submit_button("Calcular e Registrar Produção"):
                idx = opciones.index(mat_selecionado)
                item_sel = dados_combo[idx]
                
                custo_material = gramas_peca * float(item_sel["preco_por_grama"])
                custo_maquina = tempo * custo_hora
                custo_total_peca = custo_material + custo_maquina
                custo_total_ordem = custo_total_peca * qtd
                total_gramas_gastas = gramas_peca * qtd
                
                if total_gramas_gastas > float(item_sel["gramas"]):
                    st.error(f"Estoque insuficiente! Precisa de {total_gramas_gastas}g e tem {item_sel['gramas']}g.")
                else:
                    # Atualiza o estoque e insere a produção no Supabase
                    novas_gramas = float(item_sel["gramas"]) - total_gramas_gastas
                    supabase.table("estoque").update({"gramas": novas_gramas}).eq("id", item_sel["id"]).execute()
                    
                    supabase.table("producao").insert({
                        "peca": nome_peca, "material": mat_selecionado, "qtd": qtd,
                        "tempo": tempo, "gramas_usadas": total_gramas_gastas, "custo": custo_total_ordem
                    }).execute()
                    
                    st.success(f"Registrado permanentemente! Custo Total: R$ {custo_total_ordem:.2f}")

with aba3:
    st.subheader("Indicadores de Desempenho")
    dados_prod = supabase.table("producao").select("*").execute().data
    if dados_prod:
        df_prod = pd.DataFrame(dados_prod)
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Custo Total Acumulado", f"R$ {df_prod['custo'].sum():.2f}")
            fig = px.bar(df_prod, x="peca", y="custo", title="Custo por Peça")
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.metric("Total de Peças Impressas", int(df_prod['qtd'].sum()))
            fig2 = px.pie(df_prod, names="material", values="gramas_usadas", title="Consumo de Filamento (g)")
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Nenhuma produção registrada para gerar gráficos.")
