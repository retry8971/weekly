"""
MongoDB数据操作层

与ExcelDB接口一致，可作为替代数据源
集合:
  - stock_weekly_batches: 每周推荐数据
  - stock_recommenders: 推荐人统计数据
  - stock_profiles: 股票数据
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
from pymongo import MongoClient
import config


class MongoDB:
    """MongoDB数据库操作类"""
    
    def __init__(self, uri: str = None, db_name: str = None):
        self.uri = uri or config.MONGODB_URI
        self.db_name = db_name or config.MONGODB_DB
        self._client = None
        self._db = None
    
    @property
    def client(self):
        if self._client is None:
            self._client = MongoClient(self.uri)
        return self._client
    
    @property
    def db(self):
        if self._db is None:
            self._db = self.client[self.db_name]
        return self._db
    
    @property
    def recommendations(self):
        return self.db['stock_weekly_batches']
    
    @property
    def stats(self):
        return self.db['stock_recommenders']
    
    # ==================== 周数据操作 ====================
    
    def get_week_data(self, year: int, week: int) -> Dict[str, Any]:
        """获取指定周的数据"""
        doc = self.recommendations.find_one({'year': year, 'week': week})
        if not doc:
            return {'year': year, 'week': week, 'stocks': [], 'raw_text': '', 'recommender_messages': {}}
        
        # 转换格式
        return {
            'year': doc.get('year'),
            'week': doc.get('week'),
            'stocks': doc.get('stocks', []),
            'raw_text': doc.get('raw_text', ''),
            'recommender_messages': doc.get('recommender_messages', {}),
            'tracking_synced': doc.get('tracking_synced', False)
        }
    
    def save_week_data(self, year: int, week: int, stocks: List[Dict], 
                       raw_text: str = '', recommender_messages: Dict = None):
        """保存周数据"""
        doc = {
            'year': year,
            'week': week,
            'stocks': stocks,
            'raw_text': raw_text,
            'recommender_messages': recommender_messages or {},
            'updated_at': datetime.now()
        }
        self.recommendations.update_one(
            {'year': year, 'week': week},
            {'$set': doc},
            upsert=True
        )
    
    def update_stock(self, year: int, week: int, stock_name: str, updates: Dict) -> bool:
        """更新单只股票数据，返回是否成功找到并更新"""
        # 获取当前数据
        doc = self.recommendations.find_one({'year': year, 'week': week})
        if not doc:
            print(f"[UpdateStock] 未找到周数据: {year}W{week}")
            return False
        
        stocks = doc.get('stocks', [])
        found = False
        for stock in stocks:
            if stock.get('stock_name') == stock_name:
                stock.update(updates)
                found = True
                break
        
        if not found:
            print(f"[UpdateStock] 未找到股票: {stock_name}")
            return False
        
        self.recommendations.update_one(
            {'year': year, 'week': week},
            {'$set': {'stocks': stocks, 'updated_at': datetime.now()}}
        )
        return True
    
    def mark_week_tracking_synced(self, year: int, week: int):
        """标记周数据已完成股票跟踪同步"""
        self.recommendations.update_one(
            {'year': year, 'week': week},
            {'$set': {'tracking_synced': True, 'tracking_synced_at': datetime.now()}}
        )
    
    def reset_week_tracking_sync(self, year: int, week: int) -> int:
        """重置周同步状态并删除该周的跟踪数据"""
        from services import stock as stock_service
        
        # 计算周日期
        start_date, _ = stock_service.get_week_dates(year, week)
        date_str = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
        
        # 删除该周的推荐记录（从所有股票中移除该日期的推荐）
        result = self.tracking.update_many(
            {},
            {'$pull': {'recommendations': {'time': date_str}}}
        )
        
        # 重置同步标记
        self.recommendations.update_one(
            {'year': year, 'week': week},
            {'$unset': {'tracking_synced': '', 'tracking_synced_at': ''}}
        )
        
        return result.modified_count
    
    def get_all_weeks(self) -> List[Dict]:
        """获取所有周列表（包含同步状态）"""
        docs = self.recommendations.find(
            {},
            {'year': 1, 'week': 1, 'tracking_synced': 1, '_id': 0}
        ).sort([('year', -1), ('week', -1)])
        return list(docs)
    
    def delete_week(self, year: int, week: int) -> bool:
        """删除指定周数据"""
        result = self.recommendations.delete_one({'year': year, 'week': week})
        return result.deleted_count > 0
    
    def delete_stock(self, year: int, week: int, stock_name: str) -> bool:
        """删除单只股票"""
        doc = self.recommendations.find_one({'year': year, 'week': week})
        if not doc:
            return False
        
        stocks = doc.get('stocks', [])
        original_len = len(stocks)
        stocks = [s for s in stocks if s.get('stock_name') != stock_name]
        
        if len(stocks) == original_len:
            return False  # 未找到股票
        
        self.recommendations.update_one(
            {'year': year, 'week': week},
            {'$set': {'stocks': stocks, 'updated_at': datetime.now()}}
        )
        return True
    
    def update_stock_full(self, year: int, week: int, old_stock_name: str, new_data: Dict) -> bool:
        """完整更新单只股票数据（包括名称）"""
        doc = self.recommendations.find_one({'year': year, 'week': week})
        if not doc:
            return False
        
        stocks = doc.get('stocks', [])
        found = False
        for stock in stocks:
            if stock.get('stock_name') == old_stock_name:
                stock['stock_name'] = new_data.get('stock_name', stock['stock_name'])
                stock['market'] = new_data.get('market', stock.get('market'))
                stock['stock_code'] = new_data.get('stock_code', stock.get('stock_code'))
                stock['recommenders'] = new_data.get('recommenders', stock.get('recommenders', []))
                found = True
                break
        
        if not found:
            return False
        
        self.recommendations.update_one(
            {'year': year, 'week': week},
            {'$set': {'stocks': stocks, 'updated_at': datetime.now()}}
        )
        return True
    
    # ==================== 原始文本 ====================
    
    def _get_raw_text(self, year: int, week: int) -> tuple:
        """获取原始文本"""
        doc = self.recommendations.find_one({'year': year, 'week': week})
        if not doc:
            return '', {}
        return doc.get('raw_text', ''), doc.get('recommender_messages', {})
    
    def _save_raw_text(self, year: int, week: int, raw_text: str, recommender_messages: Dict):
        """保存原始文本"""
        self.recommendations.update_one(
            {'year': year, 'week': week},
            {'$set': {
                'raw_text': raw_text,
                'recommender_messages': recommender_messages or {},
                'updated_at': datetime.now()
            }},
            upsert=True
        )
    
    # ==================== 推荐人统计 ====================
    
    def get_recommender_stats(self) -> List[Dict]:
        """获取所有推荐人统计"""
        docs = self.stats.find({}, {'_id': 0}).sort('score', -1)
        return list(docs)
    
    def save_recommender_stats(self, stats_list: List[Dict]):
        """保存推荐人统计（全量覆盖）"""
        # 删除旧数据
        self.stats.delete_many({})
        # 插入新数据
        if stats_list:
            self.stats.insert_many(stats_list)
    
    # ==================== 股票跟踪 ====================
    
    @property
    def tracking(self):
        return self.db['stock_profiles']
    
    @property
    def materials(self):
        return self.db['stock_materials']
    
    # ==================== 相关资料 ====================
    
    def get_materials_by_stock(self, market: str, code: str, limit: int = 10) -> List[Dict]:
        """根据股票代码获取相关资料"""
        docs = self.materials.find(
            {'linked_stocks': {'$elemMatch': {'market': market, 'code': code}}},
            {'_id': 0, 'title': 1, 'url': 1, 'description': 1, 
             'generate_text': 1, 'material_date': 1, 'type': 1}
        ).sort('material_date', -1).limit(limit)
        return list(docs)
    
    def get_all_materials_index(self) -> Dict[str, List[Dict]]:
        """获取所有关联股票的资料索引，用于前端批量匹配"""
        docs = self.materials.find(
            {'linked_stocks': {'$ne': None}},
            {'_id': 0, 'title': 1, 'url': 1, 'linked_stocks': 1, 'material_date': 1}
        ).sort('material_date', -1)
        
        index = {}
        for doc in docs:
            for stock in doc.get('linked_stocks', []):
                key = f"{stock.get('market', '').upper()}.{stock.get('code', '')}"
                if key not in index:
                    index[key] = []
                index[key].append({
                    'title': doc.get('title'),
                    'url': doc.get('url'),
                    'date': doc.get('material_date')
                })
        return index
    
    def get_stock_tracking(self, market: str, stock_code: str) -> Optional[Dict]:
        """获取单只股票跟踪数据"""
        doc = self.tracking.find_one({'market': market, 'stock_code': stock_code})
        if doc:
            doc.pop('_id', None)
        return doc
    
    def get_all_stock_tracking(self) -> List[Dict]:
        """获取所有股票跟踪数据"""
        docs = self.tracking.find({}, {'_id': 0}).sort([('updated_at', -1)])
        return list(docs)
    
    def upsert_stock_tracking(self, market: str, stock_code: str, stock_name: str, 
                              recommendation: Dict = None):
        """更新/插入股票跟踪记录
        
        Args:
            market: 市场代码
            stock_code: 股票代码
            stock_name: 股票名称
            recommendation: 推荐记录 {"time": "2025-12-21", "recommender": "张三", "reason": "..."}
        """
        # 查找现有记录
        existing = self.tracking.find_one({'market': market, 'stock_code': stock_code})
        
        if existing:
            # 更新股票名称
            update_data = {'stock_name': stock_name, 'updated_at': datetime.now()}
            
            # 添加新推荐记录（如果有）
            if recommendation:
                # 检查是否已存在相同时间+推荐人的记录
                existing_recs = existing.get('recommendations', [])
                is_duplicate = any(
                    r.get('time') == recommendation.get('time') and 
                    r.get('recommender') == recommendation.get('recommender')
                    for r in existing_recs
                )
                if not is_duplicate:
                    self.tracking.update_one(
                        {'market': market, 'stock_code': stock_code},
                        {
                            '$set': update_data,
                            '$push': {'recommendations': recommendation}
                        }
                    )
                    return
            
            self.tracking.update_one(
                {'market': market, 'stock_code': stock_code},
                {'$set': update_data}
            )
        else:
            # 新建记录
            doc = {
                'market': market,
                'stock_code': stock_code,
                'stock_name': stock_name,
                'recommendations': [recommendation] if recommendation else [],
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
            self.tracking.insert_one(doc)
    
    def clear_stock_tracking(self):
        """清空股票跟踪集合"""
        result = self.tracking.delete_many({})
        return result.deleted_count


# 单例
_db_instance = None


def get_db():
    global _db_instance
    if _db_instance is None:
        _db_instance = MongoDB()
    return _db_instance
