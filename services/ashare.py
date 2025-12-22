# -*- coding: utf-8 -*-
"""
Ashare 股票行情数据接口

基于开源项目 https://github.com/mpquant/Ashare
用于获取A股（含北交所）股票行情数据
"""
import json
import datetime
import logging
from typing import Optional, List, Dict, Any

import requests
import pandas as pd

logger = logging.getLogger(__name__)


def get_price_day_tx(code: str, end_date: str = '', count: int = 10, frequency: str = '1d') -> pd.DataFrame:
    """腾讯日线数据获取"""
    unit = 'week' if frequency == '1w' else 'month' if frequency == '1M' else 'day'
    
    if end_date:
        if isinstance(end_date, datetime.date):
            end_date = end_date.strftime('%Y-%m-%d')
        else:
            end_date = end_date.split(' ')[0]
    
    if end_date == datetime.datetime.now().strftime('%Y-%m-%d'):
        end_date = ''
    
    url = f'http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},{unit},,{end_date},{count},qfq'
    try:
        st = json.loads(requests.get(url, timeout=10).content)

        ms = 'qfq' + unit
        stk = st['data'][code]
        buf = stk[ms] if ms in stk else stk.get(unit, [])
        
        # 检查是否有数据（北交所等可能返回空）
        if not buf:
            raise Exception(f"腾讯接口无数据（可能不支持该市场）: {code}")
        
        # 只取前6列（有些行包含分红信息作为第7列）
        buf = [row[:6] for row in buf]
        
        # 不在初始化时指定 dtype，避免日期列转换失败
        df = pd.DataFrame(buf, columns=['time', 'open', 'close', 'high', 'low', 'volume'])
        df['open'] = df['open'].astype(float)
        df['close'] = df['close'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['volume'] = df['volume'].astype(float)
        df['time'] = pd.to_datetime(df['time'])
        df.set_index(['time'], inplace=True)
        df.index.name = ''
        return df
    except Exception as e:
        raise Exception(f"腾讯日线获取失败: {code}, {e}")


def get_price_sina(code: str, end_date: str = '', count: int = 10, frequency: str = '60m') -> pd.DataFrame:
    """新浪全周期数据获取"""
    freq_map = {'1d': '240m', '1w': '1200m', '1M': '7200m'}
    frequency = freq_map.get(frequency, frequency)
    mcount = count
    ts = int(frequency[:-1]) if frequency[:-1].isdigit() else 1
    
    if end_date and frequency in ['240m', '1200m', '7200m']:
        if not isinstance(end_date, datetime.date):
            end_date = pd.to_datetime(end_date)
        unit = 4 if frequency == '1200m' else 29 if frequency == '7200m' else 1
        count = count + (datetime.datetime.now() - end_date).days // unit
    
    url = f'http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={code}&scale={ts}&ma=5&datalen={count}'
    
    try:
        res = requests.get(url, timeout=10)
        if res.status_code != 200:
            if res.status_code == 456:
                raise Exception(f"新浪数据获取失败: {code}, 频率限制")
            raise Exception(f"新浪数据获取失败: {code}, 状态码: {res.status_code}")
        raw = res.content.decode('utf-8')
        dstr = json.loads(raw)
        df = pd.DataFrame(dstr, columns=['day', 'open', 'high', 'low', 'close', 'volume'])
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        df.day = pd.to_datetime(df.day)
        df.set_index(['day'], inplace=True)
        df.index.name = ''
        
        if end_date and frequency in ['240m', '1200m', '7200m']:
            return df[df.index <= end_date][-mcount:]
        return df
    except Exception as e:
        raise e


def get_price(code: str, end_date: str = '', count: int = 10, frequency: str = '1d') -> pd.DataFrame:
    """获取股票行情数据（统一入口）"""
    xcode = code.replace('.XSHG', '').replace('.XSHE', '')
    if 'XSHG' in code:
        xcode = 'sh' + xcode
    elif 'XSHE' in code:
        xcode = 'sz' + xcode
    else:
        xcode = code
    
    if frequency in ['1d', '1w', '1M']:
        try:
            return get_price_day_tx(xcode, end_date=end_date, count=count, frequency=frequency)
        except Exception as e:
            print(f"{code}: 腾讯接口失败({e})，切换到新浪接口")
            return get_price_sina(xcode, end_date=end_date, count=count, frequency=frequency)
    
    raise ValueError(f"不支持的周期: {frequency}")


def get_kline(market: str, code: str, year: int, week: int) -> Optional[Dict[str, Any]]:
    """获取周K线数据
    
    Args:
        market: 市场代码 (sh/sz/bj)
        code: 股票代码
        year: 年份
        week: 周数
        
    Returns:
        {'open_price': float, 'close_price': float, 'change_pct': float} 或 None
    """
    from services.stock import get_week_dates
    
    try:
        start_date, end_date = get_week_dates(year, week)
        ashare_code = market + code
        
        # 格式化日期
        end_date_fmt = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
        
        print(f"Ashare获取K线: {ashare_code}, end_date={end_date_fmt}")
        
        df = get_price(ashare_code, end_date=end_date_fmt, count=5, frequency='1d')

        if df.empty:
            return None
        
        # 过滤当周数据
        start_dt = pd.to_datetime(f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}")
        end_dt = pd.to_datetime(end_date_fmt)
        week_df = df[(df.index >= start_dt) & (df.index <= end_dt)]
        
        if week_df.empty:
            return None
        
        open_price = float(week_df.iloc[0]['open'])
        close_price = float(week_df.iloc[-1]['close'])
        change_pct = round((close_price - open_price) / open_price * 100, 2)
        
        return {
            'open_price': open_price,
            'close_price': close_price,
            'change_pct': change_pct
        }
        
    except Exception as e:
        logger.error(f"Ashare获取K线失败: {market}{code}, {e}")
        return None
