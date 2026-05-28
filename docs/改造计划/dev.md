### 1. 配置文件与依赖环境

参考 [./../QUICK_START.md]

```powershell
# 激活虚拟环境
python3.10 -m venv .venv
source .venv/bin/activate          

#安装后端python依赖
pip install --upgrade pip        
pip install -r requirements.txt 

#启动docker依赖环境
#tradingagents/mongodb  暴露端口 localhost:27017
#tradingagents/redis    暴露端口 localhost:6379

# 进入项目目录
cd TradingAgentsX

# 2. 配置API密钥
cp .env.example .env
# 编辑.env文件，添加您的API密钥

# 安装前端依赖
cd frontend
npm install

# 修复安全漏洞
npm audit fix
```

### 2. 启动后端服务

```powershell
# 进入项目目录
cd TradingAgentsX    

# 启动后端
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# 或
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. 启动前端服务

```powershell
# 新开一个终端
cd d:\code\TradingAgents-CN\frontend

# 启动前端
npm run dev
# 或
npx vite
# 访问应用
http://localhost:3000/


# 历史的tradingagent
# 6. 启动应用
python -m streamlit run web/app.py

# 4. 访问应用
# 浏览器打开: http://localhost:8501
```

### 4. 登录系统

访问 `http://localhost:5173` 并登录。