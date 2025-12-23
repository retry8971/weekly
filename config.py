# 配置文件
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# Flask配置
DEBUG = True
HOST = '0.0.0.0'
PORT = 5001

# MongoDB配置
MONGODB_URI = os.getenv('MONGODB_URI', '')
MONGODB_DB = os.getenv('MONGODB_DB', '')

# Excel配置 (已废弃，保留 BASE_DIR/DATA_DIR 供其他用途)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')

# Gemini API配置（调用主系统）
GEMINI_API_URL = os.getenv('GEMINI_API_URL', '')
GEMINI_API_TOKEN = os.getenv('GEMINI_API_TOKEN', '')

# 新浪股票搜索接口
SINA_SUGGEST_URL = "http://suggest3.sinajs.cn/suggest/type=&key={key}&name=suggestdata_{timestamp}"
