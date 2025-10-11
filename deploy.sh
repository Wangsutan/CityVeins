#!/bin/bash
set -e

SERVER_IP="47.112.146.115"  # 你的服务器IP
SERVER_USER="ecs-user"
PROJECT_DIR="/opt/cityveins"
FLASK_PORT="8000"  # 使用 8000 端口

echo "🚀 开始部署 CityVeins 项目（跳过依赖安装）..."

# 1. 检查服务器端口占用
echo "🔍 检查服务器端口占用情况..."
ssh $SERVER_USER@$SERVER_IP << 'PORTCHECK'
echo "=== 端口检查 ==="
echo "80端口占用:"
sudo netstat -tulpn | grep :80 || echo "80端口空闲"
echo ""
echo "8000端口占用:"
netstat -tulpn | grep :8000 || echo "8000端口空闲"
echo "================"
PORTCHECK

# 2. 创建项目目录
ssh $SERVER_USER@$SERVER_IP "sudo mkdir -p $PROJECT_DIR && sudo chown -R $SERVER_USER:$SERVER_USER $PROJECT_DIR"

# 3. 上传项目文件
echo "📤 上传项目文件..."
rsync -avz --progress \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='*.db' \
    --exclude='output/web_save' \
    --exclude='.git' \
    --exclude='.vscode' \
    --exclude='.idea' \
    --exclude='*.log' \
    --exclude='*.pyc' \
    --include='.env' \
    ./ $SERVER_USER@$SERVER_IP:$PROJECT_DIR/

# 4. 服务器端配置（跳过依赖安装）
echo "⚙️ 配置服务器环境（跳过依赖安装）..."
ssh $SERVER_USER@$SERVER_IP << 'EOF'
set -e
cd $PROJECT_DIR

echo "=== 当前目录 ==="
pwd
ls -la

# ===== 上传环境变量文件 =====
echo "🔐 设置环境变量..."
cd $PROJECT_DIR

if [ -f ".env" ]; then
    echo "找到 .env 文件，正在设置..."
    # 设置环境变量
    set -a
    source .env
    set +a
    echo "✅ 环境变量已加载"
else
    echo "⚠️  未找到 .env 文件，请手动创建"
fi

# ===== 清理旧服务 =====
echo "🧹 清理旧服务..."
sudo systemctl stop cityveins.service 2>/dev/null || true
sudo systemctl disable cityveins.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/cityveins.service
sudo rm -f /etc/nginx/sites-available/cityveins
sudo rm -f /etc/nginx/sites-enabled/cityveins
echo "✅ 旧服务已清理"

# 只安装必要的系统依赖（Nginx）
echo "📦 检查系统依赖..."
if ! command -v nginx &> /dev/null; then
    echo "安装 Nginx..."
    sudo apt-get update -y
    sudo apt-get install -y nginx
else
    echo "✅ Nginx 已安装"
fi

# 创建必要的目录结构
echo "📁 创建目录结构..."
mkdir -p output/web_save logs static
chmod -R 755 output/ logs/ static/

# 检查 Python 环境
echo "🐍 检查 Python 环境..."
which python3 || echo "Python3 未找到"
which pip3 || echo "pip3 未找到"
python3 --version || echo "无法获取 Python 版本"

# 配置systemd服务
echo "🔧 配置systemd服务..."
sudo tee /etc/systemd/system/cityveins.service << 'SERVICE_EOF'
[Unit]
Description=CityVeins Flask Application
After=network.target

[Service]
Type=simple
User=ecs-user
WorkingDirectory=/opt/cityveins
Environment=PATH=/usr/local/bin:/usr/bin:/home/ecs-user/anaconda3/bin
EnvironmentFile=/opt/cityveins/.env
ExecStart=/home/ecs-user/anaconda3/bin/gunicorn -w 4 -b 127.0.0.1:8000 --timeout 120 --chdir /opt/cityveins/sources app:app
Restart=always
RestartSec=3

# 环境变量
Environment=PYTHONPATH=/opt/cityveins
Environment=PROJECT_ROOT=/opt/cityveins

[Install]
WantedBy=multi-user.target
SERVICE_EOF

# 配置Nginx（使用单引号避免转义问题）
echo "🌐 配置Nginx..."
sudo tee /etc/nginx/sites-available/cityveins << 'NGINX_EOF'
server {
    listen 80;
    server_name 47.112.146.115;

    # 静态文件服务（如果有的话）
    location /static/ {
        alias /opt/cityveins/static/;
        expires 30d;
    }

    # 文件下载服务
    location /download/ {
        alias /opt/cityveins/output/web_save/;
        autoindex on;
        add_header Access-Control-Allow-Origin *;
    }

    # 代理所有请求到Flask应用
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # 客户端最大body大小（用于文件上传等）
    client_max_body_size 100M;
}
NGINX_EOF

# 启用Nginx站点
sudo ln -sf /etc/nginx/sites-available/cityveins /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# 测试Nginx配置
echo "🔍 测试Nginx配置..."
sudo nginx -t
if [ $? -eq 0 ]; then
    echo "✅ Nginx 配置测试通过"
else
    echo "❌ Nginx 配置测试失败"
    exit 1
fi

# 重新加载systemd
echo "🔄 重新加载systemd..."
sudo systemctl daemon-reload

# 启用服务
echo "🔧 启用服务..."
sudo systemctl enable cityveins.service

# 启动服务
echo "🚀 启动服务..."
sudo systemctl start cityveins.service

# 重启Nginx
echo "🔄 重启Nginx..."
sudo systemctl restart nginx

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 5

# 检查服务状态
echo "📊 检查服务状态..."
sudo systemctl status cityveins.service --no-pager --lines=10

# 检查端口监听
echo "🔍 检查端口监听..."
echo "端口 8000 监听状态:"
netstat -tulpn | grep :8000 || echo "端口 8000 未监听"

echo "端口 80 监听状态:"
sudo netstat -tulpn | grep :80 || echo "端口 80 未监听"

# 配置防火墙
echo "🔥 配置防火墙..."
sudo ufw allow 80/tcp 2>/dev/null || true
sudo ufw allow 22/tcp 2>/dev/null || true

# 创建健康检查脚本
echo "📝 创建健康检查脚本..."
cat > health_check.sh << 'HEALTH_EOF'
#!/bin/bash
# CityVeins 健康检查脚本

PROJECT_DIR="/opt/cityveins"
FLASK_PORT="8000"

echo "=== CityVeins 健康检查 ==="
echo "检查时间: $(date)"
echo "项目目录: $PROJECT_DIR"
echo "Flask端口: $FLASK_PORT"

check_service() {
    service_name=$1
    if sudo systemctl is-active --quiet $service_name; then
        echo "✅ $service_name 运行正常"
        return 0
    else
        echo "❌ $service_name 服务异常"
        sudo systemctl status $service_name --no-pager --lines=5
        return 1
    fi
}

check_port() {
    port=$1
    if netstat -tuln | grep ":$port " > /dev/null; then
        echo "✅ 端口 $port 监听正常"
        return 0
    else
        echo "❌ 端口 $port 未监听"
        return 1
    fi
}

check_process() {
    process_name=$1
    if pgrep -f "$process_name" > /dev/null; then
        echo "✅ 进程 $process_name 运行中"
        return 0
    else
        echo "❌ 进程 $process_name 未运行"
        return 1
    fi
}

check_dependencies() {
    echo "=== Python 依赖检查 ==="
    python3 -c "import flask; print('✅ Flask 已安装')" 2>/dev/null || echo "❌ Flask 未安装"
    python3 -c "import flask_cors; print('✅ Flask-CORS 已安装')" 2>/dev/null || echo "❌ Flask-CORS 未安装"
    python3 -c "import pandas; print('✅ Pandas 已安装')" 2>/dev/null || echo "❌ Pandas 未安装"
    python3 -c "import gunicorn; print('✅ Gunicorn 已安装')" 2>/dev/null || echo "❌ Gunicorn 未安装"
}

# 执行检查
check_service "cityveins"
check_service "nginx"
check_port $FLASK_PORT
check_port 80
check_process "gunicorn"
check_dependencies

echo ""
echo "=== 服务日志（最近10行）==="
sudo journalctl -u cityveins -n 10 --no-pager

echo ""
echo "=== Nginx 错误日志（最近5行）==="
sudo tail -5 /var/log/nginx/error.log 2>/dev/null || echo "Nginx 错误日志不存在"

echo ""
echo "=== 应用日志（最近5行）==="
tail -5 $PROJECT_DIR/logs/*.log 2>/dev/null || echo "应用日志不存在"

echo ""
echo "健康检查完成！"
HEALTH_EOF

chmod +x health_check.sh

# 创建依赖检查脚本
echo "📝 创建依赖检查脚本..."
cat > check_dependencies.sh << 'DEP_EOF'
#!/bin/bash
echo "=== 系统依赖检查 ==="
echo "Python3: $(which python3 2>/dev/null || echo '未安装')"
echo "Pip3: $(which pip3 2>/dev/null || echo '未安装')"
echo "Gunicorn: $(which gunicorn 2>/dev/null || echo '未安装')"
echo "Nginx: $(which nginx 2>/dev/null || echo '未安装')"

echo ""
echo "=== Python 包检查 ==="
python3 -c "
try:
    import flask
    print('✅ Flask', flask.__version__)
except ImportError:
    print('❌ Flask 未安装')

try:
    import flask_cors
    print('✅ Flask-CORS 已安装')
except ImportError:
    print('❌ Flask-CORS 未安装')

try:
    import pandas
    print('✅ Pandas', pandas.__version__)
except ImportError:
    print('❌ Pandas 未安装')

try:
    import gunicorn
    print('✅ Gunicorn 已安装')
except ImportError:
    print('❌ Gunicorn 未安装')
"
DEP_EOF

chmod +x check_dependencies.sh

# 创建手动安装依赖脚本
echo "📝 创建依赖安装脚本..."
cat > install_dependencies.sh << 'INSTALL_EOF'
#!/bin/bash
echo "=== 安装 Python 依赖 ==="

# 检查 pip
if ! command -v pip3 &> /dev/null; then
    echo "安装 pip3..."
    sudo apt-get update
    sudo apt-get install -y python3-pip
fi

# 安装依赖
echo "安装 Flask..."
pip3 install flask

echo "安装 Flask-CORS..."
pip3 install flask-cors

echo "安装 Pandas..."
pip3 install pandas

echo "安装 Gunicorn..."
pip3 install gunicorn

# 安装其他可能的依赖
if [ -f "requirements.txt" ]; then
    echo "安装 requirements.txt 中的依赖..."
    pip3 install -r requirements.txt
fi

echo "✅ 所有依赖安装完成！"
INSTALL_EOF

chmod +x install_dependencies.sh

echo "✅ 服务器配置完成"

EOF

# 5. 部署后检查
echo "🔍 进行部署后检查..."
ssh $SERVER_USER@$SERVER_IP << 'POSTCHECK'
cd $PROJECT_DIR

echo "=== 部署后检查 ==="
echo "1. 检查服务状态:"
sudo systemctl status cityveins.service --no-pager --lines=3

echo ""
echo "2. 检查端口监听:"
netstat -tulpn | grep :8000 || echo "端口 8000 未监听"

echo ""
echo "3. 运行健康检查:"
./health_check.sh

echo ""
echo "4. 检查依赖:"
./check_dependencies.sh

echo ""
echo "=== 部署完成！ ==="
POSTCHECK

echo ""
echo "🎉 CityVeins 项目部署完成！"
echo ""
echo "📊 部署摘要："
echo "  - 访问地址: http://$SERVER_IP"
echo "  - 项目目录: $PROJECT_DIR"
echo "  - Flask内部端口: $FLASK_PORT"
echo "  - Nginx外部端口: 80"
echo ""
echo "🔧 管理命令："
echo "  sudo systemctl status cityveins          # 查看服务状态"
echo "  sudo systemctl restart cityveins         # 重启服务"
echo "  sudo systemctl stop cityveins            # 停止服务"
echo "  sudo journalctl -u cityveins -f          # 查看实时日志"
echo ""
echo "🛠️  工具脚本："
echo "  cd $PROJECT_DIR && ./health_check.sh     # 健康检查"
echo "  cd $PROJECT_DIR && ./check_dependencies.sh # 依赖检查"
echo "  cd $PROJECT_DIR && ./install_dependencies.sh # 安装依赖"
echo ""
echo "📋 故障排除："
echo "  如果服务启动失败，请检查："
echo "  1. Python依赖是否安装: ./check_dependencies.sh"
echo "  2. 查看详细日志: sudo journalctl -u cityveins -n 50"
echo "  3. 检查Nginx配置: sudo nginx -t"
echo "  4. 手动安装依赖: ./install_dependencies.sh"
echo ""
echo "⚠️  重要提示："
echo "  此脚本跳过了Python依赖安装！"
echo "  如果服务启动失败，请登录服务器运行:"
echo "  cd $PROJECT_DIR && ./install_dependencies.sh"
echo "  然后重启服务: sudo systemctl restart cityveins"