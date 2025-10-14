# backtest_logic.py 
import ccxt
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import riskfolio as rp
import time 

def run_backtest(tickers, benchmark_ticker, start_date, end_date, initial_capital, risk_free_rate, min_weight, max_weight):

    

    # 1. AQUISIÇÃO E PREPARAÇÃO DOS DADOS (COM CCXT E PAGINAÇÃO)
   
    print("Iniciando download de dados com CCXT (com paginação)...")
    exchange = ccxt.binance()
    ccxt_tickers = [ticker.replace('-USD', '/USDT') for ticker in tickers]
    all_prices = {}
    
    # Converte a data de início para o formato de timestamp que o CCXT espera
    start_timestamp = exchange.parse8601(start_date.strftime('%Y-%m-%d') + 'T00:00:00Z')

    for ticker in ccxt_tickers:
        try:
            # --- Início da Lógica de Paginação ---
            all_ohlcv = []
            since = start_timestamp
            
            while True:
                print(f"  - Buscando dados para {ticker} a partir de {exchange.iso8601(since)}")
                # Pede um lote de dados
                ohlcv = exchange.fetch_ohlcv(ticker, timeframe='1d', since=since)
                
                # Se a corretora não retornar mais dados, o período acabou, então saia do loop
                if not ohlcv:
                    break
                
                # Adiciona o lote de dados recém-baixado à nossa lista principal
                all_ohlcv.extend(ohlcv)
                
                # Prepara a próxima busca pegando o timestamp do último dado recebido (+1ms)
                since = ohlcv[-1][0] + 1
                
                # Faz uma pequena pausa para não sobrecarregar a API da corretora
                time.sleep(exchange.rateLimit / 1000)
            # --- Fim da Lógica de Paginação ---

            if not all_ohlcv:
                print(f"  - {ticker}: Nenhum dado retornado.")
                continue

            temp_df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            temp_df['date'] = pd.to_datetime(temp_df['timestamp'], unit='ms')
            temp_df.set_index('date', inplace=True)
            all_prices[ticker.replace('/USDT', '-USD')] = temp_df['close']
            print(f"  - {ticker}: Download completo!")
        except Exception as e:
            print(f"  - {ticker}: FALHA - {e}")
            continue
            
    if not all_prices:
        print("ERRO: Nenhum dado de preço foi baixado com sucesso.")
        return (None,) * 10 

    price_df = pd.DataFrame(all_prices)
    # Filtra o DataFrame para garantir que ele respeite a data de início e fim selecionada
    price_df = price_df.loc[start_date:end_date]
    price_df.dropna(axis=0, how='any', inplace=True)
    daily_returns = price_df.pct_change().dropna()

    if daily_returns.empty or benchmark_ticker not in price_df.columns:
        print("ERRO: Dados insuficientes para o backtest após a limpeza.")
        return (None,) * 10

   
    # 2. LÓGICA DE BACKTESTING COM REBALANCEAMENTO 
   
    print("Iniciando simulação de backtesting...")
    weights_history = pd.DataFrame(index=daily_returns.index, columns=daily_returns.columns)
    final_mu = None
    final_cov = None
    for i in range(len(daily_returns)):
        current_date = daily_returns.index[i]
        if i == 0 or (daily_returns.index[i-1].quarter != current_date.quarter):
            historic_returns = daily_returns.iloc[:i+1]
            if historic_returns.shape[0] < 2: continue
            mu = historic_returns.mean() * 252
            cov = historic_returns.cov() * 252
            final_mu = mu
            final_cov = cov
            port = rp.Portfolio(returns=historic_returns)
            port.lower_bound = min_weight # Limite inferior para cada ativo
            port.upper_bound = max_weight # Limite superior para cada ativo           
            port.mu = mu
            port.cov = cov


            w = port.optimization(model='Classic', rm='MV', obj='Sharpe', rf=risk_free_rate)
            if w is not None: weights_history.loc[current_date] = w.T.values[0]
        else:
            weights_history.loc[current_date] = weights_history.iloc[i-1]
    weights_history.ffill(inplace=True); weights_history.bfill(inplace=True)
    portfolio_daily_returns = (weights_history * daily_returns).sum(axis=1)
    portfolio_value_over_time = initial_capital * (1 + portfolio_daily_returns).cumprod()
    

    # 3. CÁLCULO DE MÉTRICAS (VAR E OUTROS) (sem alterações)
   
    print("Calculando métricas de desempenho...")
    var_results = {"var_percent": 0, "var_value": 0}
    if not portfolio_daily_returns.empty:
        var_historic = portfolio_daily_returns.quantile(1 - 0.95)
        var_results = {"var_percent": var_historic, "var_value": portfolio_value_over_time.iloc[-1] * abs(var_historic)}
    benchmark_returns = price_df[benchmark_ticker].pct_change().dropna()
    benchmark_value_over_time = initial_capital * (1 + benchmark_returns).cumprod()
    def calculate_performance_metrics(value_series, risk_free_rate_local):
        daily_pct_change = value_series.pct_change().dropna()
        if daily_pct_change.empty or value_series.iloc[0] == 0: return {"Retorno Total": 0, "Retorno Anualizado": 0, "Volatilidade Anualizada": 0, "Índice de Sharpe": 0}
        total_return = (value_series.iloc[-1] / value_series.iloc[0]) - 1
        years = max((value_series.index[-1] - value_series.index[0]).days / 365.25, 1/365.25)
        annualized_return = (1 + total_return)**(1/years) - 1
        annualized_volatility = daily_pct_change.std() * np.sqrt(252)
        sharpe_ratio = (annualized_return - risk_free_rate_local) / annualized_volatility if annualized_volatility != 0 else 0
        return {"Retorno Total": total_return, "Retorno Anualizado": annualized_return, "Volatilidade Anualizada": annualized_volatility, "Índice de Sharpe": sharpe_ratio}
    portfolio_metrics = calculate_performance_metrics(portfolio_value_over_time, risk_free_rate)
    benchmark_metrics = calculate_performance_metrics(benchmark_value_over_time, risk_free_rate)
    
   
    # 4. GERAÇÃO DOS GRÁFICOS 
   
    print("Gerando gráficos...")
    plt.style.use('seaborn-v0_8-darkgrid')
    fig1, ax1 = plt.subplots(figsize=(12, 6)); ax1.set_title('Crescimento do Capital', fontsize=16); ax1.plot(portfolio_value_over_time, label='Carteira Otimizada', color='blue'); ax1.plot(benchmark_value_over_time, label=f'Benchmark ({benchmark_ticker})', color='grey', linestyle='--'); ax1.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f'${x:,.0f}')); ax1.set_ylabel('Valor da Carteira (USD)'); ax1.legend(); ax1.grid(True)
    fig2, ax2 = plt.subplots(figsize=(12, 6)); ax2.set_title('Evolução da Alocação de Ativos', fontsize=16); ax2.stackplot(weights_history.index, weights_history.T, labels=weights_history.columns, alpha=0.8); ax2.yaxis.set_major_formatter(mtick.PercentFormatter(1.0)); ax2.legend(loc='upper left'); ax2.set_ylabel('Percentual da Carteira'); ax2.grid(True)
    
    print("Lógica do backtest finalizada. Retornando resultados.")
    
   
    # 5. RETORNO DOS RESULTADOS PARA A INTERFACE 
    
    return (portfolio_metrics, benchmark_metrics, var_results, fig1, fig2, 
            portfolio_value_over_time, benchmark_value_over_time, weights_history, 
            final_mu, final_cov)

    
    