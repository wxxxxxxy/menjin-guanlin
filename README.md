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
sudo systemctl status doubao.service

# 停止服务
sudo systemctl stop doubao.service

# 重启服务
sudo systemctl restart doubao.service

# 查看服务日志（实时）
sudo journalctl -u doubao.service -f

# 查看历史日志（最近100行）
sudo journalctl -u doubao.service -n 100

如何设置定时重启
Orange Pi Zero3（Linux 系统）最稳定、通用的定时重启方法是用 crontab 定时任务，下面给你完整步骤与常用示例。
一、准备工作
用 SSH 或串口登录 Zero3，确保系统时间正确（否则定时不准）：
bash
date  # 查看时间
sudo timedatectl set-timezone Asia/Shanghai  # 设为北京时间
确认 reboot 命令可用：
bash
sudo reboot  # 测试重启（会立即重启，谨慎执行）
二、用 crontab 设置定时重启（推荐）
方法 1：编辑用户 crontab（简单）
bash
sudo crontab -e  # 以root权限编辑（必须sudo，否则重启权限不足）
首次打开会让你选编辑器，选 nano（输入1回车）即可。
在文件末尾添加一行（按需求选示例）：
常用定时示例（cron 格式：分 时 日 月 周）
bash
# 每天凌晨4点整重启（最常用）
0 4 * * * /sbin/shutdown -r now

# 每天凌晨2点30分重启
30 2 * * * /sbin/shutdown -r now

# 每周一、三、五凌晨3点重启
0 3 * * 1,3,5 /sbin/shutdown -r now

# 每月1号、15号凌晨5点重启
0 5 1,15 * * /sbin/shutdown -r now

# 每6小时重启一次（0点、6点、12点、18点）
0 */6 * * * /sbin/shutdown -r now
保存退出（nano 编辑器）
按 Ctrl+O → 回车（确认保存）
按 Ctrl+X → 退出
验证任务
bash
sudo crontab -l  # 列出当前定时任务，确认已添加
