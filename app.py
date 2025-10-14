import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from backtest_logic import run_backtest

# Configuração da página (mantida)
st.set_page_config(
    layout="wide",
    page_title="Simulador de Carteira de Criptoativos com Otimização de Risco",
    initial_sidebar_state="expanded"
)

# Função auxiliar para formatar os números para o padrão brasileiro
def format_currency(value):
    s = f"{value:_.2f}".replace('.', ',').replace('_', '.')
    return f"${s}"

st.title("Simulador de Carteira de Criptoativos com Otimização de Risco")
st.markdown("Use o painel à esquerda para configurar as configurações e clique em 'Executar Simulação' para ver os resultados.")

# --- Barra Lateral ---
st.sidebar.header("Parâmetros da Simulação")
all_tickers = ['BTC-USD', 'ETH-USD', 'ADA-USD', 'SOL-USD', 'XRP-USD', 'DOT-USD', 'DOGE-USD', 'LTC-USD', 'LINK-USD', 'MATIC-USD']
selected_tickers = st.sidebar.multiselect("Selecione os Ativos:", options=all_tickers, default=['BTC-USD', 'ETH-USD', 'ADA-USD', 'SOL-USD', 'XRP-USD'])
start_date = st.sidebar.date_input("Data de Início", datetime(2021, 1, 1))
end_date = st.sidebar.date_input("Data de Fim", datetime.now())
initial_capital = st.sidebar.number_input("Capital Inicial (USD)", min_value=100, value=10000, step=100)
risk_free_rate = st.sidebar.slider("Taxa Livre de Risco Anual (%)", 0.0, 5.0, 2.0, 0.1) / 100

# Sliders para as restrições de peso
st.sidebar.subheader("Restrições de Alocação")
min_weight = st.sidebar.slider(
    "Peso Mínimo por Ativo (%)",
    min_value=0.0,
    max_value=25.0,
    value=5.0,
    step=0.5,
    help="Força cada ativo a ter pelo menos esta porcentagem na carteira durante o rebalanceamento."
) / 100.0

max_weight = st.sidebar.slider(
    "Peso Máximo por Ativo (%)",
    min_value=10.0,
    max_value=100.0,
    value=50.0,
    step=1.0,
    help="Impede que qualquer ativo ultrapasse esta porcentagem na carteira durante o rebalanceamento."
) / 100.0


if st.sidebar.button("Executar Simulação"):
    # Validações
    if not selected_tickers:
        st.warning("Por favor, selecione pelo menos um ativo.")
    elif min_weight * len(selected_tickers) > 1:
        st.sidebar.error(f"A soma dos pesos mínimos ({min_weight*len(selected_tickers):.0%}) não pode exceder 100%. Reduza o peso mínimo ou o número de ativos.")
    elif min_weight > max_weight:
        st.sidebar.error("O peso mínimo não pode ser maior que o peso máximo.")
    else:
        with st.spinner("Buscando dados e realizando o backtest... Isso pode levar um momento."):
            results = run_backtest(
                tickers=selected_tickers, benchmark_ticker='BTC-USD', start_date=start_date,
                end_date=end_date, initial_capital=initial_capital, risk_free_rate=risk_free_rate,
                min_weight=min_weight, max_weight=max_weight
            )
            (portfolio_metrics, benchmark_metrics, var_results, fig_capital, fig_allocation,
             portfolio_value, benchmark_value, weights_df, final_mu, final_cov) = results

        if portfolio_metrics is None:
            st.error("Não foi possível obter dados. Tente outros ativos ou um período de tempo diferente.")
        else:
            st.success("Simulação Concluída!")
            st.subheader("Métricas de Desempenho")
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### Carteira Otimizada")
                with st.container(border=True):
                    st.metric(label="Retorno Total", value=f"{portfolio_metrics['Retorno Total']:.2%}", help="O ganho ou perda percentual total da carteira do início ao fim do período.")
                with st.container(border=True):
                    st.metric(label="Retorno Anualizado", value=f"{portfolio_metrics['Retorno Anualizado']:.2%}", help="A taxa de retorno média por ano. Ajuda a comparar investimentos com durações diferentes.")
                with st.container(border=True):
                    st.metric(label="Índice de Sharpe", value=f"{portfolio_metrics['Índice de Sharpe']:.2f}", help="Mede o retorno ajustado ao risco. Quanto maior, melhor o desempenho em relação ao risco corrido. Acima de 1 é considerado bom.")
                with st.container(border=True):
                    st.metric(label="Valor em Risco (VaR 95%)", value=f"{var_results['var_percent']:.2%}", help="A perda diária máxima esperada para um dia de negociação, com 95% de confiança.")
                    st.markdown(f"**Perda Máx. Diária:** {format_currency(var_results['var_value'])}")
            with col2:
                st.markdown("#### Referência (Comprar e Manter BTC)")
                with st.container(border=True):
                    st.metric(label="Retorno Total", value=f"{benchmark_metrics['Retorno Total']:.2%}")
                with st.container(border=True):
                    st.metric(label="Retorno Anualizado", value=f"{benchmark_metrics['Retorno Anualizado']:.2%}")
                with st.container(border=True):
                    st.metric(label="Índice de Sharpe", value=f"{benchmark_metrics['Índice de Sharpe']:.2f}")
            st.subheader("Análise Gráfica"); st.markdown("---")
            st.pyplot(fig_capital)
            final_portfolio_str = format_currency(portfolio_value.iloc[-1])
            final_benchmark_str = format_currency(benchmark_value.iloc[-1])
            if portfolio_value.iloc[-1] > benchmark_value.iloc[-1]:
                st.success(f"**Análise do Resultado:** A estratégia de otimização superou o benchmark, terminando com {final_portfolio_str} contra {final_benchmark_str} do benchmark.")
            else:
                st.warning(f"**Análise do Resultado:** A estratégia otimizada teve um desempenho inferior ao benchmark, terminando com {final_portfolio_str} contra {final_benchmark_str} do benchmark.")
            
            # <<< TEXTO COMPLETO 1 >>>
            with st.expander("ℹ️ Entenda o Gráfico de Crescimento do Capital"):
                st.markdown("""
                    Este gráfico compara a evolução do valor da sua carteira otimizada (linha azul) com o desempenho de um investimento simples de "comprar e segurar" o benchmark, que é o Bitcoin (linha cinza tracejada).
                    - **Eixo Y (Vertical):** Mostra o valor total da carteira em dólares (USD).
                    - **Eixo X (Horizontal):** Representa a passagem do tempo.
                    
                    O objetivo é que a linha azul (sua carteira) termine acima da linha cinza, indicando que a estratégia de rebalanceamento e otimização gerou mais retorno do que simplesmente ter comprado Bitcoin no início do período.
                """)

            st.pyplot(fig_allocation)
            final_weights = weights_df.iloc[-1].sort_values(ascending=False)
            analysis_text_lines = ["**Análise da Alocação Final:** A carteira, após o último rebalanceamento, foi composta por:"]
            for asset, weight in final_weights.items():
                if weight > 0.0001:
                    analysis_text_lines.append(f"- **{asset}:** {weight:.2%}")
            full_analysis_text = "\n".join(analysis_text_lines)
            st.info(full_analysis_text)

            # <<< TEXTO COMPLETO 2 >>>
            with st.expander("ℹ️ Entenda o Gráfico de Evolução da Alocação"):
                st.markdown("""
                    Este é um gráfico de área empilhada que mostra como os pesos (a porcentagem de alocação) de cada criptoativo na sua carteira mudaram ao longo do tempo.
                    - **Cada cor representa um ativo diferente**, como indicado na legenda.
                    - **A altura de cada cor** em um determinado ponto no tempo mostra a porcentagem daquele ativo na carteira.
                    - **As mudanças abruptas** acontecem nos momentos de rebalanceamento (a cada trimestre), quando o otimizador calcula os novos pesos ideais com base no histórico de retornos e volatilidade.
                    
                    Este gráfico ajuda a entender quais ativos o otimizador priorizou em diferentes momentos do mercado.
                """)

            st.subheader("Indicadores por Ativo (Dados do Último Rebalanceamento)"); st.markdown("---")
            if final_mu is not None and final_cov is not None:
                volatility = pd.Series(np.sqrt(np.diag(final_cov)), index=final_mu.index)
                sharpe_individual = (final_mu - risk_free_rate) / volatility
                summary_df = pd.DataFrame({'Retorno Anualizado': final_mu, 'Volatilidade Anualizada': volatility, 'Índice de Sharpe Individual': sharpe_individual, 'Peso Final na Carteira': weights_df.iloc[-1]})
                st.dataframe(summary_df.style.format({'Retorno Anualizado': '{:.2%}', 'Volatilidade Anualizada': '{:.2%}', 'Índice de Sharpe Individual': '{:.2f}', 'Peso Final na Carteira': '{:.2%}'}))
                
                # <<< TEXTO COMPLETO 3 >>>
                with st.expander("ℹ️ Entenda a Tabela de Indicadores"):
                    st.markdown("""
                        Esta tabela mostra os dados que o otimizador usou para tomar suas decisões durante o **último rebalanceamento** do período. A estratégia busca alocar mais capital em ativos com um alto **Índice de Sharpe Individual**.

                        - **Retorno Anualizado:** A expectativa de retorno para o ativo com base em seu histórico.
                        - **Volatilidade Anualizada:** O grau de risco (variação de preço) do ativo. Menor volatilidade significa menos risco.
                        - **Índice de Sharpe Individual:** A relação entre o retorno e a volatilidade de cada ativo. Este é o principal indicador que o otimizador usa para avaliar a atratividade de um ativo. Valores mais altos são melhores.
                        - **Peso Final na Carteira:** A porcentagem de capital que a estratégia alocou para cada ativo após o último rebalanceamento, com base nos indicadores acima.
                    """)
else:
    st.info("Aguardando configuração para iniciar a simulação.")

