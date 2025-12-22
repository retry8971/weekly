"""
股票查询服务

提供股票代码查询和K线数据获取
"""
import re
import time
import requests
from urllib.parse import quote
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
import config


def search_stock(stock_name: str) -> Optional[Dict[str, str]]:
    """通过新浪接口搜索股票代码（与原系统一致）
    
    Args:
        stock_name: 股票名称
        
    Returns:
        {'market': 'sh/sz/bj', 'code': '600000', 'name': '浦发银行'} 或 None
    """
    # 检查是否已经是股票代码格式
    if re.match(r'^\d{6}$', stock_name):
        market = _get_market_from_code(stock_name)
        return {'market': market.lower(), 'code': stock_name, 'name': None}
    
    timestamp = str(int(time.time() * 1000))
    # 原系统使用的URL格式
    url = f"http://suggest3.sinajs.cn/suggest/key={quote(stock_name)}&name=suggestdata_{timestamp}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "http://finance.sina.com.cn/"
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            print(f"[SearchStock] API错误: {stock_name}, status={resp.status_code}")
            return None
        
        # 新浪接口返回 GBK 编码
        content = resp.content.decode('gbk', errors='ignore')
        print(f"[SearchStock] 响应: {stock_name} -> {content[:200]}")
        
        match = re.search(r'="([^"]+)"', content)
        if not match:
            print(f"[SearchStock] 正则匹配失败: {stock_name}")
            return None
        
        data_str = match.group(1)
        if not data_str:
            print(f"[SearchStock] 空数据: {stock_name}")
            return None
        
        # 解析结果：格式为 股票名,市场类型,代码,市场代码,简称,...;
        # A股: 星图测控,11,920116,bj920116,星图测控,,星图测控,99,1,,,
        # 港股: 第四范式,31,06682,06682,第四范式,,第四范式,99,1,,,
        items = data_str.split(';')
        for item in items:
            if not item.strip():
                continue
            parts = item.split(',')
            if len(parts) > 4:
                name = parts[0]  # 股票名称（用于矫正）
                market_type = parts[1]  # 市场类型：11=A股, 31=港股, 41=美股
                code = parts[2]  # 股票代码
                code_full = parts[3]  # 市场+代码，如 bj920116 或 06682
                
                # 港股: 市场类型 31，5位数字代码
                if market_type == '31' and re.match(r'^\d{5}$', code):
                    print(f"[SearchStock] 成功(港股): {stock_name} -> HK.{code} ({name})")
                    return {'market': 'HK', 'code': code, 'name': name}
                
                # A股: 6位数字 -> 从 code_full 提取市场
                if re.match(r'^\d{6}$', code):
                    market = code_full.replace(code, '').upper()  # bj920116.replace(920116, '') = bj -> BJ
                    if market in ['SH', 'SZ', 'BJ']:
                        print(f"[SearchStock] 成功: {stock_name} -> {market}.{code} ({name})")
                        return {'market': market, 'code': code, 'name': name}
        
        print(f"[SearchStock] 未匹配: {stock_name}")
        return None
        
    except Exception as e:
        print(f"[SearchStock] 异常: {stock_name}, {type(e).__name__}: {e}")
        return None


def _get_market_from_code(code: str) -> str:
    """根据股票代码判断市场"""
    if code.startswith(('60', '68')):
        return 'SH'
    elif code.startswith(('00', '30')):
        return 'SZ'
    elif code.startswith(('8', '4', '9')):
        return 'BJ'
    return 'SZ'


def get_week_dates(year: int, week: int) -> Tuple[str, str]:
    """获取指定周的起止日期"""
    # ISO周从周一开始
    jan4 = datetime(year, 1, 4)
    start = jan4 - timedelta(days=jan4.weekday()) + timedelta(weeks=week-1)
    end = start + timedelta(days=4)  # 周五
    return start.strftime('%Y%m%d'), end.strftime('%Y%m%d')


def get_kline(market: str, code: str, year: int, week: int) -> Optional[Dict[str, Any]]:
    """获取K线数据（使用ashare接口）
    
    Args:
        market: 'sh' 或 'sz'
        code: 股票代码
        year: 年份
        week: 周数
        
    Returns:
        {'open_price': float, 'close_price': float, 'change_pct': float} 或 None
    """
    try:
        from services.ashare import get_kline as ashare_get_kline
        return ashare_get_kline(market, code, year, week)
    except Exception as e:
        print(f"[K线] 获取失败: {market}{code}, {e}")
        return None
