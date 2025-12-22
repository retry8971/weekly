"""
推荐服务

提供推荐文本解析、股票代码填充、K线获取、推荐人统计计算
"""
import re
import requests
from typing import Dict, Any, List, Tuple
from datetime import datetime
from services.excel_db import get_db
from services import stock as stock_service
import config


class RecommendationService:
    """推荐服务"""
    
    def __init__(self):
        self.db = get_db()
    
    # ==================== 提交和解析 ====================
    
    def submit_raw_text(self, year: int, week: int, raw_text: str) -> Dict[str, Any]:
        """提交原始文本（仅保存，不解析）"""
        # 保存原始文本
        self.db._save_raw_text(year, week, raw_text, {})
        return {'year': year, 'week': week, 'saved': True}
    
    def parse_with_gemini(self, year: int, week: int) -> Dict[str, Any]:
        """调用Gemini API解析推荐文本"""
        import traceback
        
        # 获取原始文本
        raw_text, _ = self.db._get_raw_text(year, week)
        if not raw_text:
            return {'error': '未找到原始文本'}
        
        # 调用主系统Gemini API
        try:
            prompt = self._build_parse_prompt(raw_text)
            print(f"[Gemini] 开始解析 {year}年第{week}周, 文本长度: {len(raw_text)}")
            
            parsed_items = self._call_gemini_api(raw_text, prompt)
            print(f"[Gemini] 解析结果: {len(parsed_items)} 条记录")
            
            if not parsed_items:
                return {'error': 'Gemini返回空结果，请检查原始文本格式'}
            
            # 合并相同股票
            merged, recommender_messages = self._merge_recommendations(parsed_items)
            print(f"[Gemini] 合并后: {len(merged)} 只股票, {len(recommender_messages)} 位推荐人")
            
            # 构建股票列表
            stocks = []
            for stock_name, recommenders in merged.items():
                stocks.append({
                    'stock_name': stock_name,
                    'recommenders': list(recommenders),
                    'status': 'pending'
                })
            
            # 保存到Excel
            self.db.save_week_data(year, week, stocks, raw_text, recommender_messages)
            print(f"[Gemini] 保存成功: {len(stocks)} 只股票")
            
            return {
                'year': year, 
                'week': week, 
                'stocks_count': len(stocks),
                'recommenders_count': len(recommender_messages)
            }
            
        except Exception as e:
            error_detail = traceback.format_exc()
            print(f"[Gemini] 解析失败:\n{error_detail}")
            return {'error': f"{str(e)}\n\n详细信息:\n{error_detail}"}
    
    def _build_parse_prompt(self, raw_text: str) -> str:
        """构建Gemini解析提示词（与原系统一致）"""
        return """你是一个股票推荐信息提取专家。请仔细解析以下股票推荐文本，提取每一条推荐中的推荐人和股票名称。

**重要：请确保不遗漏任何一条推荐记录！**

解析规则：
1. 每行通常以序号开头，后面是推荐人名字，再后面是推荐内容
2. 提取推荐人名字（序号后的第一个词或短语，注意从语义上剔除重复，例如:名字A 名字A 看好xxx）
3. 提取所有提到的股票名称，多只股票用空格分隔，如果股票名称不完整，请结合他的推荐逻辑来推断股票对应的股票名称
4. 如果只有股票代码没有名称，请转换为对应的股票名称
5. 忽略方向性描述词汇（如"看好"、"继续"、"主线"、"关注"等）
6. 如果某条没有具体股票名称则跳过
7. 保留推荐人的原始完整消息（去掉序号前缀）"""
    
    def _call_gemini_api(self, text: str, prompt: str) -> List[Dict]:
        """调用主系统Gemini API
        
        主系统接口: POST /api/gemini/generate/text
        请求体: {"text": "输入文本", "prompt": "提示词"}
        响应: {"errcode": 0, "data": {"content": "..."}}
        """
        import json
        
        if not config.GEMINI_API_TOKEN:
            raise ValueError("未配置GEMINI_API_TOKEN")
        
        
        resp = requests.post(
            config.GEMINI_API_URL,
            json={
                'text': text,
                'prompt': prompt,
                'use_structured_response': True,
                'response_format': {"items": [{"name": "推荐人", "stocks": "股票1 股票2", "original": "原始推荐消息"}]}
            },
            headers={'Token': config.GEMINI_API_TOKEN},
            timeout=600
        )
        
        if resp.status_code != 200:
            raise Exception(f"Gemini API错误: {resp.status_code}, {resp.text}")
        
        result = resp.json()
        print(f"[Gemini] API响应: {json.dumps(result, ensure_ascii=False)[:500]}")
        
        if result.get('errcode', 0) != 0:
            raise Exception(f"Gemini API错误: {result.get('msg', '未知错误')}")
        
        # content直接在顶级，不是在data里
        content = result.get('content', '')
        
        # 解析JSON并展开（与原系统一致）
        try:
            parsed = json.loads(content)
            items = parsed.get('items', []) if isinstance(parsed, dict) else parsed
            
            # 展开：每个股票一条记录
            expanded = []
            for item in items:
                name = item.get('name', '').strip()
                stocks_str = item.get('stocks', '')
                original = item.get('original', '').strip()
                if name and stocks_str:
                    for stock in stocks_str.split():
                        if stock.strip():
                            expanded.append({
                                'recommender': name,
                                'stock': stock.strip(),
                                'original': original
                            })
            print(f"[Gemini] 展开后: {len(expanded)} 条记录")
            return expanded
        except json.JSONDecodeError as e:
            print(f"[Gemini] JSON解析失败: {e}, 内容: {content[:500]}")
            return []
    
    def _merge_recommendations(self, items: List[Dict]) -> Tuple[Dict, Dict]:
        """合并相同股票的推荐（与原系统一致）"""
        merged = {}  # stock -> set of recommenders
        recommender_messages = {}  # recommender -> original message
        
        for item in items:
            recommender = item.get('recommender', '').strip()
            stock = item.get('stock', '').strip()
            original = item.get('original', '').strip()
            
            if recommender and stock:
                if stock not in merged:
                    merged[stock] = set()
                merged[stock].add(recommender)
                
                # 保存推荐人原始消息（只保存第一次出现的），剔除开头的推荐人名字
                if recommender and original and recommender not in recommender_messages:
                    msg = original
                    if msg.startswith(recommender):
                        msg = msg[len(recommender):].lstrip(' :：\t')
                    recommender_messages[recommender] = msg
        
        return merged, recommender_messages
    
    # ==================== 股票代码解析 ====================
    
    def resolve_stock_codes(self, year: int, week: int) -> Dict[str, Any]:
        """解析股票代码"""
        data = self.db.get_week_data(year, week)
        stocks = data.get('stocks', [])
        
        print(f"[ResolveCode] 开始解析 {year}年第{week}周, 共 {len(stocks)} 只股票")
        
        # 第一步：按股票名称去重，合并推荐人
        name_map = {}  # key: stock_name, value: stock dict
        for stock in stocks:
            stock_name = stock.get('stock_name', '')
            if not stock_name:
                continue
            
            if stock_name not in name_map:
                name_map[stock_name] = stock.copy()
            else:
                # 合并推荐人
                existing = name_map[stock_name]
                existing_recommenders = set(existing.get('recommenders', []))
                new_recommenders = set(stock.get('recommenders', []))
                existing['recommenders'] = list(existing_recommenders | new_recommenders)
                # 如果已有代码，保留
                if stock.get('market') and stock.get('stock_code'):
                    existing['market'] = stock['market']
                    existing['stock_code'] = stock['stock_code']
                    existing['status'] = stock.get('status', 'resolved')
        
        # 转回列表
        stocks = list(name_map.values())
        name_dedup_count = len(data.get('stocks', [])) - len(stocks)
        if name_dedup_count > 0:
            print(f"[ResolveCode] 按名称去重: 合并 {name_dedup_count} 条重复记录")
        
        success = 0
        error = 0
        
        for stock in stocks:
            stock_name = stock.get('stock_name', '')
            print(f"[ResolveCode] 处理: {stock_name}, 已有market={stock.get('market')}, code={stock.get('stock_code')}")
            
            if stock.get('market') and stock.get('stock_code'):
                print(f"[ResolveCode] 跳过: {stock_name} (已有代码)")
                continue  # 已有代码
            
            result = stock_service.search_stock(stock_name)
            print(f"[ResolveCode] 搜索结果: {stock_name} -> {result}")
            
            if result:
                stock['market'] = result['market']
                stock['stock_code'] = result['code']
                stock['status'] = 'resolved'
                # 如果返回了正确的股票名，则矫正
                if result.get('name') and result['name'] != stock_name:
                    print(f"[ResolveCode] 矫正股票名: {stock_name} -> {result['name']}")
                    stock['stock_name'] = result['name']
                success += 1
            else:
                error += 1
        
        # 第二步：按市场+代码去重合并
        code_map = {}  # key: "market_code", value: stock dict
        for stock in stocks:
            market = stock.get('market', '')
            code = stock.get('stock_code', '')
            
            if not market or not code:
                # 没有代码的股票直接保留
                key = f"_no_code_{stock.get('stock_name', '')}"
                code_map[key] = stock
                continue
            
            key = f"{market}_{code}"
            
            if key not in code_map:
                code_map[key] = stock
            else:
                # 合并推荐人
                existing = code_map[key]
                existing_recommenders = set(existing.get('recommenders', []))
                new_recommenders = set(stock.get('recommenders', []))
                existing['recommenders'] = list(existing_recommenders | new_recommenders)
        
        # 转回列表
        merged_stocks = list(code_map.values())
        code_dedup_count = len(stocks) - len(merged_stocks)
        if code_dedup_count > 0:
            print(f"[ResolveCode] 按代码去重: 合并 {code_dedup_count} 条重复记录")
        
        # 保存最终结果
        self.db.save_week_data(
            year, week, merged_stocks,
            data.get('raw_text', ''),
            data.get('recommender_messages', {})
        )
        
        merged_count = name_dedup_count + code_dedup_count
        print(f"[ResolveCode] 完成: success={success}, error={error}, merged={merged_count}")
        return {'success': success, 'error': error, 'merged': merged_count}
    
    def _merge_duplicate_stocks(self, year: int, week: int) -> int:
        """合并相同市场+代码的股票"""
        data = self.db.get_week_data(year, week)
        stocks = data.get('stocks', [])
        
        # 按 market+code 分组
        stock_map = {}  # key: "market_code", value: {"stock": merged_stock, "indices": [原始索引]}
        
        for i, stock in enumerate(stocks):
            market = stock.get('market', '')
            code = stock.get('stock_code', '')
            
            if not market or not code:
                continue  # 跳过没有代码的
            
            key = f"{market}_{code}"
            
            if key not in stock_map:
                stock_map[key] = {'stock': stock.copy(), 'indices': [i]}
            else:
                # 合并推荐人
                existing = stock_map[key]['stock']
                existing_recommenders = set(existing.get('recommenders', []))
                new_recommenders = set(stock.get('recommenders', []))
                merged_recommenders = list(existing_recommenders | new_recommenders)
                existing['recommenders'] = merged_recommenders
                stock_map[key]['indices'].append(i)
        
        # 检查是否有重复
        duplicates = [v for v in stock_map.values() if len(v['indices']) > 1]
        
        if not duplicates:
            return 0
        
        # 构建新的股票列表
        indices_to_remove = set()
        for dup in duplicates:
            # 保留第一个，移除其他
            for idx in dup['indices'][1:]:
                indices_to_remove.add(idx)
        
        # 更新第一个股票的推荐人
        for dup in duplicates:
            first_idx = dup['indices'][0]
            stocks[first_idx]['recommenders'] = dup['stock']['recommenders']
        
        # 移除重复项
        new_stocks = [s for i, s in enumerate(stocks) if i not in indices_to_remove]
        
        # 保存
        self.db.save_week_data(
            year, week, new_stocks,
            data.get('raw_text', ''),
            data.get('recommender_messages', {})
        )
        
        merged_count = len(indices_to_remove)
        print(f"[ResolveCode] 去重合并: 移除 {merged_count} 条重复记录")
        return merged_count
    
    # ==================== K线数据 ====================
    
    def fetch_kline_data(self, year: int, week: int) -> Dict[str, Any]:
        """获取K线数据"""
        data = self.db.get_week_data(year, week)
        stocks = data.get('stocks', [])
        
        success = 0
        error = 0
        
        for stock in stocks:
            market = stock.get('market')
            code = stock.get('stock_code')
            
            if not market or not code:
                print(f"[FetchKline] 跳过无代码: {stock.get('stock_name')}")
                error += 1
                continue
            
            try:
                kline = stock_service.get_kline(market, code, year, week)
                if kline:
                    updated = self.db.update_stock(year, week, stock['stock_name'], {
                        'open_price': kline['open_price'],
                        'close_price': kline['close_price'],
                        'change_pct': kline['change_pct'],
                        'status': 'completed'
                    })
                    if updated:
                        success += 1
                    else:
                        print(f"[FetchKline] 更新失败: {stock['stock_name']} (数据库未找到)")
                        error += 1
                else:
                    print(f"[FetchKline] K线为空: {market}.{code} {stock.get('stock_name')}")
                    error += 1
            except Exception as e:
                print(f"[FetchKline] 异常: {market}.{code} {stock.get('stock_name')} - {e}")
                error += 1
            
            import time
            time.sleep(0.3)
        
        print(f"[FetchKline] 完成: success={success}, error={error}")
        return {'success': success, 'error': error}
    
    # ==================== 排行榜 ====================
    
    def get_ranking(self, year: int, week: int) -> Dict[str, Any]:
        """获取排行榜数据"""
        data = self.db.get_week_data(year, week)
        stocks = data.get('stocks', [])
        
        # 获取推荐人评级
        stats = self.db.get_recommender_stats()
        ratings = {s['name']: s.get('rating', 'D') for s in stats}
        
        # 分离有涨跌幅和无涨跌幅的股票
        with_pct = [s for s in stocks if s.get('change_pct') is not None]
        without_pct = [s for s in stocks if s.get('change_pct') is None]
        
        # 有涨跌幅的按涨跌幅排序，无涨跌幅的接在后面
        sorted_with_pct = sorted(with_pct, key=lambda x: x.get('change_pct', 0), reverse=True)
        sorted_stocks = sorted_with_pct + without_pct
        
        # 计算周日期范围
        start_date, end_date = stock_service.get_week_dates(year, week)
        week_start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
        week_end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
        
        return {
            'stocks': sorted_stocks,
            'recommender_messages': data.get('recommender_messages', {}),
            'recommender_ratings': ratings,
            'raw_text': data.get('raw_text', ''),
            'week_start': week_start,
            'week_end': week_end
        }
    
    # ==================== 推荐人统计 ====================
    
    def calculate_recommender_stats(self) -> Dict[str, Any]:
        """计算推荐人统计"""
        weeks = self.db.get_all_weeks()
        
        # 收集所有推荐人数据
        recommender_data = {}  # name -> {weeks: {(y,w): [returns]}, details: []}
        
        for w in weeks:
            data = self.db.get_week_data(w['year'], w['week'])
            for stock in data.get('stocks', []):
                change_pct = stock.get('change_pct')
                if change_pct is None:
                    continue
                
                for recommender in stock.get('recommenders', []):
                    if recommender not in recommender_data:
                        recommender_data[recommender] = {'weeks': {}, 'details': []}
                    
                    week_key = (w['year'], w['week'])
                    if week_key not in recommender_data[recommender]['weeks']:
                        recommender_data[recommender]['weeks'][week_key] = []
                    
                    recommender_data[recommender]['weeks'][week_key].append(change_pct)
                    recommender_data[recommender]['details'].append({
                        'year': w['year'],
                        'week': w['week'],
                        'stock_name': stock['stock_name'],
                        'change_pct': change_pct
                    })
        
        # 计算统计
        result = []
        for name, data in recommender_data.items():
            weekly_returns = []
            net_value = 1.0
            total_count = 0
            win_count = 0
            
            sorted_weeks = sorted(data['weeks'].keys())
            weekly_returns_list = []
            
            for week_key in sorted_weeks:
                week_returns = data['weeks'][week_key]
                week_avg = sum(week_returns) / len(week_returns)
                weekly_returns.append(week_avg)
                net_value *= (1 + week_avg / 100)
                
                weekly_returns_list.append({
                    'year': week_key[0],
                    'week': week_key[1],
                    'return': round(week_avg, 2),
                    'net_value': round(net_value, 4),
                    'stock_count': len(week_returns)
                })
                
                total_count += len(week_returns)
                win_count += sum(1 for r in week_returns if r > 0)
            
            total_return = (net_value - 1) * 100
            avg_return = sum(weekly_returns) / len(weekly_returns) if weekly_returns else 0
            win_rate = (win_count / total_count * 100) if total_count > 0 else 0
            positive_weeks = sum(1 for r in weekly_returns if r > 0)
            negative_weeks = sum(1 for r in weekly_returns if r < 0)
            total_weeks = len(weekly_returns)
            
            # 评分计算
            win_rate_score = min(win_rate, 100)
            return_score = min(max(total_return + 50, 0), 100)
            avg_score = min(max((avg_return + 5) * 10, 0), 100)
            weeks_score = min(total_weeks / 6 * 100, 100) if total_weeks >= 3 else total_weeks / 3 * 50
            count_score = min(total_count / 15 * 100, 100) if total_count >= 5 else total_count / 5 * 50
            
            weeks_bonus = 0
            if total_weeks >= 4:
                if positive_weeks == total_weeks:
                    weeks_bonus = min(75 + (total_weeks - 4) * 5, 100)
                elif negative_weeks == total_weeks:
                    weeks_bonus = max(-50 - (total_weeks - 4) * 5, -100)
                elif negative_weeks > positive_weeks:
                    weeks_bonus = -(negative_weeks / total_weeks) * 50
                else:
                    weeks_bonus = (positive_weeks / total_weeks) * 50
            
            confidence = min(total_weeks / 2, 1.0)
            raw_score = (
                win_rate_score * 0.22 +
                return_score * 0.23 +
                avg_score * 0.15 +
                weeks_score * 0.10 +
                count_score * 0.10 +
                weeks_bonus * 0.20
            )
            score = round(50 + (raw_score - 50) * confidence, 1)
            
            if score >= 80:
                rating = "S"
            elif score >= 65:
                rating = "A"
            elif score >= 45:
                rating = "B"
            elif score >= 25:
                rating = "C"
            else:
                rating = "D"
            
            weekly_win_rate = (positive_weeks / total_weeks * 100) if total_weeks > 0 else 0
            
            sorted_details = sorted(data['details'], key=lambda x: (x['year'], x['week']), reverse=True)
            sorted_weekly = sorted(weekly_returns_list, key=lambda x: (x['year'], x['week']), reverse=True)
            
            result.append({
                'name': name,
                'total_count': total_count,
                'win_count': win_count,
                'win_rate': round(win_rate, 2),
                'positive_weeks': positive_weeks,
                'weeks_count': total_weeks,
                'weekly_win_rate': round(weekly_win_rate, 2),
                'total_return': round(total_return, 2),
                'avg_return': round(avg_return, 2),
                'score': score,
                'rating': rating,
                'weekly_returns': sorted_weekly,
                'details': sorted_details
            })
        
        # 按分数排序并保存
        result.sort(key=lambda x: x['score'], reverse=True)
        self.db.save_recommender_stats(result)
        
        return {'recommenders': result, 'count': len(result)}
    
    def get_recommender_stats(self) -> Dict[str, Any]:
        """获取推荐人统计"""
        stats = self.db.get_recommender_stats()
        return {'recommenders': stats}
    
    # ==================== 股票跟踪 ====================
    
    def sync_stock_tracking(self, year: int, week: int, force: bool = False) -> Dict[str, Any]:
        """同步周推荐数据到股票跟踪集合（批量分析版）
        
        Args:
            force: 是否强制重新同步（忽略已同步标记）
        """
        data = self.db.get_week_data(year, week)
        recommender_messages = data.get('recommender_messages', {})
        
        # 检查是否已同步
        if not force and data.get('tracking_synced'):
            print(f"[StockTracking] {year}年第{week}周: 已同步，跳过")
            return {'synced': 0, 'skipped': True}
        
        if not recommender_messages:
            print(f"[StockTracking] {year}年第{week}周: 无推荐原文")
            return {'synced': 0}
        
        # 计算周开始日期
        start_date, _ = stock_service.get_week_dates(year, week)
        date_str = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
        
        # 1. 批量调用 Gemini 分析所有推荐原文
        analysis_result = self._batch_analyze_recommendations(recommender_messages)
        
        if not analysis_result:
            print(f"[StockTracking] {year}年第{week}周: Gemini分析失败")
            return {'synced': 0}
        
        # 2. 遍历分析结果，填充代码并入库
        synced = 0
        for stock_name, recommenders_data in analysis_result.items():
            # 查询股票代码
            stock_info = stock_service.search_stock(stock_name)
            if not stock_info:
                print(f"[StockTracking] 跳过: {stock_name} (未找到代码)")
                continue
            
            market = stock_info['market']
            code = stock_info['code']
            name = stock_info.get('name') or stock_name
            
            # 遍历推荐人
            for recommender, reason in recommenders_data.items():
                recommendation = {
                    'time': date_str,
                    'recommender': recommender,
                    'reason': reason if reason else '无具体逻辑'
                }
                
                self.db.upsert_stock_tracking(market, code, name, recommendation)
                synced += 1
        
        # 3. 标记已同步
        if synced > 0:
            self.db.mark_week_tracking_synced(year, week)
        
        print(f"[StockTracking] 同步 {year}年第{week}周: {synced} 条推荐记录")
        return {'synced': synced}
    
    def _batch_analyze_recommendations(self, recommender_messages: Dict[str, str]) -> Dict[str, Dict[str, str]]:
        """批量分析推荐原文，提取股票-推荐人-逻辑映射
        
        Returns:
            {"股票名": {"推荐人A": "逻辑", "推荐人B": "逻辑"}}
        """
        # 构建输入文本
        input_lines = []
        for recommender, message in recommender_messages.items():
            if message:
                input_lines.append(f"【{recommender}】{message}")
        
        if not input_lines:
            return {}
        
        input_text = "\n".join(input_lines)
        
        prompt = """任务：分析以下股票推荐原文，提取每只股票及其推荐人和推荐逻辑。

要求：
1. 识别原文中提到的所有股票名称
2. 对每只股票，找出推荐该股票的推荐人
3. 提取该推荐人针对该股票的具体推荐逻辑（如有），简洁概括不超过50字
4. 如果推荐人只是提及股票名称而无具体逻辑，该股票的逻辑留空
5. 排除方向性词汇如"看好"、"关注"等，只保留实质性逻辑
"""
        
        try:
            resp = requests.post(
                config.GEMINI_API_URL,
                json={
                    'text': input_text,
                    'prompt': prompt,
                    'use_structured_response': True,
                    'response_format': {"items": [{"stock": "股票名称", "recommenders": [{"name": "推荐人名", "reason": "推荐逻辑"}]}]}
                },
                headers={'Token': config.GEMINI_API_TOKEN},
                timeout=600
            )
            
            if resp.status_code != 200:
                print(f"[StockTracking] Gemini API错误: {resp.status_code}")
                return {}
            
            result = resp.json()
            if result.get('errcode', 0) != 0:
                print(f"[StockTracking] Gemini错误: {result.get('msg')}")
                return {}
            
            content = result.get('content', '')
            
            # 解析JSON
            import json
            # 清理可能的markdown代码块
            if content.startswith('```'):
                content = content.split('\n', 1)[1] if '\n' in content else content
                if content.endswith('```'):
                    content = content[:-3]
            content = content.strip()
            
            raw_parsed = json.loads(content)
            
            # 转换为期望的格式: {"股票名": {"推荐人": "逻辑"}}
            parsed = {}
            items = raw_parsed.get('items', [])
            for item in items:
                stock_name = item.get('stock', '')
                if not stock_name:
                    continue
                recommenders_list = item.get('recommenders', [])
                parsed[stock_name] = {}
                for rec in recommenders_list:
                    name = rec.get('name', '')
                    reason = rec.get('reason', '')
                    if name:
                        parsed[stock_name][name] = reason
            
            print(f"[StockTracking] Gemini分析完成: {len(parsed)} 只股票")
            return parsed
            
        except json.JSONDecodeError as e:
            print(f"[StockTracking] JSON解析失败: {e}, 内容: {content[:200]}")
            return {}
        except Exception as e:
            print(f"[StockTracking] 分析失败: {e}")
            return {}
    
    def sync_all_stock_tracking(self) -> Dict[str, Any]:
        """从所有周数据同步到股票跟踪"""
        weeks = self.db.get_all_weeks()
        total_synced = 0
        
        for week_info in weeks:
            year = week_info['year']
            week = week_info['week']
            result = self.sync_stock_tracking(year, week)
            total_synced += result.get('synced', 0)
        
        print(f"[StockTracking] 全量同步完成: {total_synced} 条记录")
        return {'weeks': len(weeks), 'synced': total_synced}
    
    def get_all_stock_tracking(self) -> Dict[str, Any]:
        """获取所有股票跟踪数据"""
        stocks = self.db.get_all_stock_tracking()
        return {'stocks': stocks, 'count': len(stocks)}
    
    def get_stock_tracking(self, market: str, stock_code: str) -> Dict[str, Any]:
        """获取单只股票跟踪数据"""
        stock = self.db.get_stock_tracking(market, stock_code)
        return {'stock': stock}


# 单例
_service_instance = None

def get_service() -> RecommendationService:
    global _service_instance
    if _service_instance is None:
        _service_instance = RecommendationService()
    return _service_instance
