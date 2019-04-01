# RSRS相对强弱模型 日线
# 导入函数库
from jqdata import *
import pandas as pd
import numpy as np
import statsmodels.api as sm
from datetime import datetime,timedelta


# 初始化函数，设定基准等等
def initialize(context):
    # 设定参数
    set_params(context)
    # 设定回测规则
    set_backtest()

    # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
    # 开盘时运行
    run_daily(market_open, time='open', reference_security='000300.XSHG')
    # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')


def set_params(context):
    # 设置RSRS指标中N, M的值
    #统计周期
    g.N = 18
    #统计样本长度
    g.M = 1200
    #首次运行判断
    g.init = True
    #风险参考基准
    g.security1 = '000300.XSHG'
    #记录策略运行天数
    g.days = 0
    # 买入阈值
    g.buy = 0.7
    g.sell = -0.7

    # RSRS信号的预先计算
    # 用于记录回归后的beta值，即斜率
    g.ans = []
    # 用于计算被决定系数加权修正后的贝塔值
    g.ans_rightdev= []
    
    # 计算2005年1月5日至回测开始日期的RSRS斜率指标
    prices = get_price(g.security1, '2005-01-05', context.previous_date, '1d', ['high', 'low'])
    highs = prices.high
    lows = prices.low
    g.ans = []
    for i in range(len(highs))[g.N:]:
        data_high = highs.iloc[i-g.N+1:i+1]
        data_low = lows.iloc[i-g.N+1:i+1]
        X = sm.add_constant(data_low)
        model = sm.OLS(data_high,X)
        results = model.fit()
        g.ans.append(results.params[1])
        #计算r2
        g.ans_rightdev.append(results.rsquared)    
        
    
#3 设置回测条件
def set_backtest():
    set_benchmark(g.security1)       # 设置为基准
    set_option('use_real_price', True) # 用真实价格交易
    set_option('order_volume_ratio', 1)# 放大买入限制
    log.set_level('order', 'error')    # 设置报错等级
    # 股票类每笔交易时的手续费是：买入时佣金千1，卖出时佣金千1，印花税千1, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.001, close_commission=0.001, min_commission=5), type='stock')


## 开盘前运行函数
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))


## 开盘时运行函数
def market_open(context):
    # RSRS信号
    # 填入各个日期的RSRS斜率值
    beta=0
    r2=0
    if g.init:
        g.init = False
    else:
        #RSRS斜率指标定义
        prices = attribute_history(g.security1, g.N, '1d', ['high', 'low'])
        highs = prices.high
        lows = prices.low
        X = sm.add_constant(lows)
        model = sm.OLS(highs, X)
        beta = model.fit().params[1]
        g.ans.append(beta)
        #计算r2
        r2=model.fit().rsquared
        g.ans_rightdev.append(r2)
    # 计算均值序列    
    section = g.ans[-g.M:]
    # 计算均值序列
    mu = np.mean(section)
    # 计算标准化RSRS指标序列
    sigma = np.std(section)
    zscore = (section[-1]-mu)/sigma  
    #计算右偏RSRS标准分
    zscore_rightdev= zscore*beta*r2
    
    # 取得当前的现金
    cash = context.portfolio.available_cash
    
    # 如果上一时间点的RSRS斜率大于买入阈值, 则全仓买入
    if zscore_rightdev > g.buy:
        # 记录这次买入
        log.info("RSRS大于买入阈值, 买入 %s" % g.security1)
        # 用所有 cash 买入股票
        order_value(g.security1, cash)
    # 如果上一时间点的RSRS斜率小于卖出阈值, 则空仓卖出
    elif zscore_rightdev < g.sell and context.portfolio.positions[g.security1].closeable_amount > 0:
        # 记录这次卖出
        log.info("RSRS小于卖出阈值, 卖出 %s" % g.security1)
        # 卖出所有股票,使这只股票的最终持有量为0
        order_target(g.security1, 0)


## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')
