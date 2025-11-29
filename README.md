# menjin-guanlin
冠林门禁-香橙派zero3-巴法
1. 创建 systemd 服务文件
在/etc/systemd/system/目录下创建服务文件（例如doubao.service）：sudo nano /etc/systemd/system/doubao3.service

写入以下内容（根据实际路径调整）：
[Unit]
Description=Doubao Device Control Service
After=network.target  # 网络就绪后启动
StartLimitIntervalSec=500  # 重启限制时间窗口（秒）
StartLimitBurst=5          # 时间窗口内最大重启次数

[Service]
User=orangepi  # 运行用户（香橙派默认用户）
Group=orangepi
WorkingDirectory=/home/orangepi  # 程序工作目录（根据实际修改）
ExecStart=/usr/bin/python3 /home/orangepi/doubao.py  # 程序绝对路径
Restart=always  # 任何情况都自动重启
RestartSec=5    # 重启间隔（秒）
KillMode=mixed  # 优雅终止进程
TimeoutStopSec=30  # 停止超时时间
StandardOutput=journal  # 输出重定向到系统日志
StandardError=journal
SyslogIdentifier=doubao  # 日志标识（方便筛选）

[Install]
WantedBy=multi-user.target  # 多用户模式下启动

2. 启用并启动服务
# 重新加载systemd配置
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start doubao.service

# 设置开机自启
sudo systemctl enable doubao.service

3. 服务管理命令
 # 查看服务状态
sudo systemctl status doubao3.service

# 停止服务
sudo systemctl stop doubao3.service

# 重启服务
sudo systemctl restart doubao3.service

# 查看服务日志（实时）
sudo journalctl -u doubao3.service -f

# 查看历史日志（最近100行）
sudo journalctl -u doubao3.service -n 100
