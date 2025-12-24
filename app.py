"""
股票推荐系统 - Flask主程序
"""
from flask import Flask, jsonify, request, send_from_directory, redirect
from datetime import datetime
import os

import config
from services.recommendation import get_service

app = Flask(__name__, static_folder='static')


# ==================== 静态页面 ====================

@app.route('/')
def index():
    return send_from_directory('static', 'ranking.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)


# ==================== 公开API ====================

@app.route('/api/recommendation/<int:year>/<int:week>/ranking', methods=['GET'])
def get_ranking(year, week):
    """获取排行榜数据"""
    service = get_service()
    data = service.get_ranking(year, week)
    return jsonify({'data': data})


@app.route('/api/recommendation/recommenders', methods=['GET'])
def get_recommenders():
    """获取推荐人统计"""
    service = get_service()
    data = service.get_recommender_stats()
    return jsonify({'data': data})


# ==================== 管理API ====================

@app.route('/api/admin/weeks', methods=['GET'])
def get_weeks():
    """获取所有周列表"""
    from services.mongodb_db import get_db
    db = get_db()
    weeks = db.get_all_weeks()
    return jsonify({'data': weeks})


import requests
from flask import Flask, jsonify, request, send_from_directory, redirect, Response

# ... (imports)

@app.route('/open_url')
def open_url():
    """代理访问外部链接"""
    target = request.args.get('target')
    if not target:
        return "Missing target URL", 400
    
    try:
        # 简单的代理实现
        resp = requests.get(target, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }, timeout=10)
        
        # 过滤掉部分响应头以避免冲突
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [(name, value) for (name, value) in resp.headers.items() 
                   if name.lower() not in excluded_headers]
        
        return Response(resp.content, resp.status_code, headers)
    except Exception as e:
        return f"Proxy Error: {str(e)}", 500


@app.route('/api/admin/week/<int:year>/<int:week>', methods=['GET'])
def get_week_detail(year, week):
    """获取周详情"""
    from services.mongodb_db import get_db
    db = get_db()
    data = db.get_week_data(year, week)
    return jsonify({'data': data})


@app.route('/api/admin/submit', methods=['POST'])
def submit_raw_text():
    """提交原始文本"""
    data = request.json
    year = data.get('year')
    week = data.get('week')
    raw_text = data.get('raw_text', '')
    
    if not year or not week:
        return jsonify({'error': '缺少年份或周数'}), 400
    
    service = get_service()
    result = service.submit_raw_text(year, week, raw_text)
    return jsonify({'data': result})


@app.route('/api/admin/parse', methods=['POST'])
def parse_recommendations():
    """Gemini解析推荐"""
    data = request.json
    year = data.get('year')
    week = data.get('week')
    
    if not year or not week:
        return jsonify({'error': '缺少年份或周数'}), 400
    
    service = get_service()
    result = service.parse_with_gemini(year, week)
    
    if 'error' in result:
        return jsonify({'error': result['error']}), 500
    
    return jsonify({'data': result})


@app.route('/api/admin/resolve-codes', methods=['POST'])
def resolve_codes():
    """填充股票代码"""
    data = request.json
    year = data.get('year')
    week = data.get('week')
    
    if not year or not week:
        return jsonify({'error': '缺少年份或周数'}), 400
    
    service = get_service()
    result = service.resolve_stock_codes(year, week)
    return jsonify({'data': result})


@app.route('/api/admin/fetch-kline', methods=['POST'])
def fetch_kline():
    """获取K线数据"""
    data = request.json
    year = data.get('year')
    week = data.get('week')
    
    if not year or not week:
        return jsonify({'error': '缺少年份或周数'}), 400
    
    service = get_service()
    result = service.fetch_kline_data(year, week)
    return jsonify({'data': result})


@app.route('/api/admin/recalculate-stats', methods=['POST'])
def recalculate_stats():
    """重算推荐人统计"""
    service = get_service()
    result = service.calculate_recommender_stats()
    return jsonify({'data': {'count': result.get('count', 0)}})


@app.route('/api/admin/delete-week', methods=['POST'])
def delete_week():
    """删除周数据"""
    data = request.json
    year = data.get('year')
    week = data.get('week')
    
    if not year or not week:
        return jsonify({'error': '缺少年份或周数'}), 400
    
    from services.mongodb_db import get_db
    db = get_db()
    success = db.delete_week(year, week)
    return jsonify({'data': {'deleted': success}})


@app.route('/api/admin/delete-stock', methods=['POST'])
def delete_stock():
    """删除单个股票"""
    data = request.json
    year = data.get('year')
    week = data.get('week')
    stock_name = data.get('stock_name')
    
    if not year or not week or not stock_name:
        return jsonify({'error': '缺少必要参数'}), 400
    
    from services.mongodb_db import get_db
    db = get_db()
    success = db.delete_stock(year, week, stock_name)
    return jsonify({'data': {'deleted': success}})


@app.route('/api/admin/update-stock', methods=['POST'])
def update_stock():
    """修改股票信息"""
    data = request.json
    year = data.get('year')
    week = data.get('week')
    old_stock_name = data.get('old_stock_name')
    new_data = data.get('new_data', {})
    
    if not year or not week or not old_stock_name:
        return jsonify({'error': '缺少必要参数'}), 400
    
    from services.mongodb_db import get_db
    db = get_db()
    success = db.update_stock_full(year, week, old_stock_name, new_data)
    return jsonify({'data': {'updated': success}})


@app.route('/api/admin/current-week', methods=['GET'])
def get_current_week():
    """获取当前周信息"""
    now = datetime.now()
    year, week, _ = now.isocalendar()
    return jsonify({'data': {'year': year, 'week': week}})


@app.route('/api/admin/search-stock', methods=['GET'])
def search_stock_api():
    """搜索股票代码"""
    stock_name = request.args.get('name', '')
    if not stock_name:
        return jsonify({'error': '缺少股票名称'}), 400
    
    from services import stock as stock_service
    result = stock_service.search_stock(stock_name)
    if result:
        return jsonify({'data': result})
    else:
        return jsonify({'data': None})


# ==================== 股票跟踪 API ====================

@app.route('/api/stock-tracking', methods=['GET'])
def get_all_stock_tracking():
    """获取所有股票跟踪数据"""
    service = get_service()
    result = service.get_all_stock_tracking()
    return jsonify({'data': result})


@app.route('/api/stock-tracking/<market>/<code>', methods=['GET'])
def get_stock_tracking(market, code):
    """获取单只股票跟踪数据"""
    service = get_service()
    result = service.get_stock_tracking(market.upper(), code)
    return jsonify({'data': result})


@app.route('/api/admin/sync-tracking', methods=['POST'])
def sync_stock_tracking():
    """同步股票跟踪数据"""
    service = get_service()
    result = service.sync_all_stock_tracking()
    return jsonify({'data': result})


@app.route('/api/admin/clear-tracking', methods=['POST'])
def clear_stock_tracking():
    """清空股票跟踪数据"""
    from services.mongodb_db import get_db
    db = get_db()
    deleted = db.clear_stock_tracking()
    return jsonify({'data': {'deleted': deleted}})


@app.route('/api/admin/reset-week-sync/<int:year>/<int:week>', methods=['POST'])
def reset_week_sync(year, week):
    """重置周同步状态并删除该周跟踪数据"""
    from services.mongodb_db import get_db
    db = get_db()
    deleted = db.reset_week_tracking_sync(year, week)
    return jsonify({'data': {'success': True, 'deleted': deleted}})


# ==================== 研报管理 API ====================

REPORTS_DIR = os.path.join(os.path.dirname(__file__), 'reports')

@app.route('/api/reports', methods=['GET'])
def list_reports():
    """获取所有研报列表"""
    if not os.path.exists(REPORTS_DIR):
        return jsonify({'data': []})
    
    reports = []
    # 优先查找 .url 文件，其次是 .html 文件
    # 实际上由于互斥逻辑，每个 code 应该只有其中一种
    files = os.listdir(REPORTS_DIR)
    
    # 收集所有的 stock_code
    codes = set()
    for f in files:
        if f.endswith('.html') or f.endswith('.url'):
            codes.add(f.rsplit('.', 1)[0])
            
    for code in codes:
        url_file = f"{code}.url"
        html_file = f"{code}.html"
        
        if url_file in files:
            # 读取 URL 内容
            try:
                with open(os.path.join(REPORTS_DIR, url_file), 'r', encoding='utf-8') as f:
                    url = f.read().strip()
                reports.append({
                    'stock_code': code,
                    'type': 'link',
                    'url': url,
                    'filename': url_file
                })
            except Exception as e:
                print(f"Error reading {url_file}: {e}")
        elif html_file in files:
            reports.append({
                'stock_code': code,
                'type': 'file',
                'url': f"/reports/{html_file}",
                'filename': html_file
            })
            
    return jsonify({'data': reports})


@app.route('/api/reports/upload', methods=['POST'])
def upload_report():
    """
    上传研报
    type: 'file' | 'link'
    file: (if type=file)
    link: (if type=link)
    stock_code: required
    """
    stock_code = request.form.get('stock_code', '').strip()
    report_type = request.form.get('type', 'file')
    
    if not stock_code:
        return jsonify({'error': '缺少股票代码'}), 400

    # 确保目录存在
    os.makedirs(REPORTS_DIR, exist_ok=True)
    
    # 清理旧文件 (互斥)
    old_html = os.path.join(REPORTS_DIR, f'{stock_code}.html')
    old_url = os.path.join(REPORTS_DIR, f'{stock_code}.url')
    if os.path.exists(old_html): os.remove(old_html)
    if os.path.exists(old_url): os.remove(old_url)
    
    if report_type == 'link':
        link = request.form.get('link', '').strip()
        if not link:
            return jsonify({'error': '缺少链接地址'}), 400
        
        # 保存 .url 文件
        with open(os.path.join(REPORTS_DIR, f'{stock_code}.url'), 'w', encoding='utf-8') as f:
            f.write(link)
        
        return jsonify({'data': {'saved': True, 'stock_code': stock_code, 'type': 'link'}})
        
    else: # type == 'file'
        if 'file' not in request.files:
            return jsonify({'error': '未上传文件'}), 400
        
        file = request.files['file']
        if not file.filename.endswith('.html'):
            return jsonify({'error': '只支持 HTML 文件'}), 400
        
        # 保存 .html 文件
        file.save(os.path.join(REPORTS_DIR, f'{stock_code}.html'))
        
        return jsonify({'data': {'saved': True, 'stock_code': stock_code, 'type': 'file'}})


@app.route('/api/reports/<stock_code>', methods=['DELETE'])
def delete_report(stock_code):
    """删除研报 (同时尝试删除 .html 和 .url)"""
    deleted = False
    
    html_path = os.path.join(REPORTS_DIR, f'{stock_code}.html')
    if os.path.exists(html_path):
        os.remove(html_path)
        deleted = True
        
    url_path = os.path.join(REPORTS_DIR, f'{stock_code}.url')
    if os.path.exists(url_path):
        os.remove(url_path)
        deleted = True
        
    if deleted:
        return jsonify({'data': {'deleted': True}})
    return jsonify({'error': '文件不存在'}), 404


@app.route('/reports/<path:filename>')
def serve_report(filename):
    """静态访问研报文件"""
    return send_from_directory(REPORTS_DIR, filename)


# ==================== 错误处理 ====================

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': str(e)}), 500


# ==================== 启动 ====================

if __name__ == '__main__':
    print(f"启动股票推荐系统...")
    print(f"访问: http://localhost:{config.PORT}/")
    print(f"管理: http://localhost:{config.PORT}/admin.html")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
