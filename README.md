# 📊 股票推荐系统（独立版）

一个独立运行的股票推荐管理系统，基于 Flask 和 Excel 存储。

## 📋 功能

- **Gemini AI 解析**：调用主系统 API 自动提取推荐人和股票
- **股票代码填充**：通过新浪接口自动查询股票代码
- **K线数据同步**：获取周涨跌幅数据
- **推荐人统计**：胜率、收益率、综合评分计算
- **数据管理**：按周管理推荐数据

---

## 🚀 快速开始

### Windows

```powershell
# 1. 进入目录
cd weekly

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动服务
python app.py
```

### macOS

```bash
# 1. 进入目录
cd weekly

# 2. 安装依赖
pip3 install -r requirements.txt

# 3. 启动服务
python3 app.py
```

---

## 🌐 访问地址

启动后访问：

| 页面 | 地址 |
|------|------|
| 排行榜 | http://localhost:5001/ |
| 推荐人 | http://localhost:5001/recommender.html |
| 管理后台 | http://localhost:5001/admin.html |

---

## 📖 使用流程

1. **保存文本** - 在管理后台粘贴推荐原始文本
2. **Gemini解析** - AI 自动提取推荐人和股票名称
3. **填充代码** - 自动查询股票代码（市场+代码）
4. **同步股价** - 获取周开盘/收盘价和涨跌幅
5. **重算统计** - 更新推荐人综合评分

---

## 📁 数据存储

支持两种数据源（通过环境变量配置）：

### Excel（默认）

```bash
# 默认使用 Excel
python app.py
```

数据保存在 `data/recommendations.xlsx`

### MongoDB

```bash
# 使用 MongoDB
export DATA_SOURCE=mongodb
export MONGODB_URI="mongodb+srv://user:pass@cluster.mongodb.net/"
export MONGODB_DB="nebula"
python app.py
```

---

## 📌 注意事项

- Python 版本：3.9+
- 首次使用需确保主系统 Gemini API 可访问
- Excel模式无需额外配置，MongoDB需设置环境变量

