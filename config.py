# 配置文件
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# Flask配置
DEBUG = True
HOST = '0.0.0.0'
PORT = 5001

# 数据源配置: 'excel' 或 'mongodb'
DATA_SOURCE = os.getenv('DATA_SOURCE', 'mongodb')

# Excel数据目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
EXCEL_FILE = os.path.join(DATA_DIR, 'recommendations.xlsx')

# MongoDB配置
MONGODB_URI = os.getenv('MONGODB_URI', '')
MONGODB_DB = os.getenv('MONGODB_DB', '')

# Gemini API配置（调用主系统）
GEMINI_API_URL = os.getenv('GEMINI_API_URL', '')
GEMINI_API_TOKEN = os.getenv('GEMINI_API_TOKEN', '')

# 新浪股票搜索接口
SINA_SUGGEST_URL = "http://suggest3.sinajs.cn/suggest/type=&key={key}&name=suggestdata_{timestamp}"
