# -*- coding: utf-8 -*-
import socket
import threading
import time
import logging
import os
import signal
from logging.handlers import RotatingFileHandler


# ========== 日志优化：文件轮转+持久化（兼容Windows测试） ==========
def setup_logger():
    # 改为orangepi用户可写的路径（_home目录下）
    log_dir = "/home/orangepi/doubao_logs/"  # 普通用户有权限创建和写入
    os.makedirs(log_dir, exist_ok=True)  # 确保日志目录存在
    log_file = os.path.join(log_dir, "device_control.log")

    # 配置日志轮转：单个文件50MB，最多保留10个备份
    handler = RotatingFileHandler(
        log_file,
        maxBytes=50 * 1024 * 1024,  # 50MB
        backupCount=10,
        encoding='utf-8'
    )
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(process)d:%(threadName)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)

    log = logging.getLogger()
    log.setLevel(logging.INFO)  # 生产环境用INFO，测试时可改为DEBUG
    log.addHandler(handler)
    log.addHandler(logging.StreamHandler())  # 同时输出到控制台
    return log


log = setup_logger()

# 全局变量优化
tcp_client_socket = None
tcp_lock = threading.Lock()  # TCP连接线程安全锁

# ========== 先定义设备类型枚举常量（修复NameError的核心） ==========
DEVICE_DIKU = "diku"
DEVICE_DONGMEN = "dongmen"
DEVICE_YILOU = "yilou"

# ========== 再定义设备配置字典（引用上面的常量） ==========
device_configs = {
    DEVICE_DIKU: {
        "damen_ip": "192.168.3.12",
        "topic": "fxJB63mYW006",
        "udp_pack_template": "08ff010800000000000000000000000053470000e40800003300000000002800e40800000101010032000100000000001479cb0131000100000000000000000032aaf0a000010000"
    },
    DEVICE_DONGMEN: {
        "damen_ip": "192.168.0.20",
        "topic": "eCE5rY9Xa006",
        "udp_pack_template": "08ff010800000000000000000000000053470000010a00003300000000002800010a00000101010032000100000000001479cb0130000100000000000000000032aaf0a000010000"
    },
    DEVICE_YILOU: {
        "damen_ip": "192.168.3.11",
        "topic": "bnv7cDLpM006",
        "udp_pack_template": "08ff010800000000000000000000000053470000b60900003300000000002800b60900000101010032000100000000001479cb0131000100000000000000000032aaf0a000010000"
    }
}

# 其他全局常量（放在后面不影响）
CLIENT_IP = "192.168.3.68"
UID = "e1e20b4af75c4cdea761bb7ee4689462"
TCP_SERVER = ("bemfa.com", 8344)


# ========== 设备解锁客户端类 ==========
class UnlockClient:
    def __init__(self, device_type):
        self.device_type = device_type
        self.config = device_configs[device_type]
        self.random_index = 1
        self.random_n = '01'
        self.udp_socket = None
        self._init_udp_socket()

    def _init_udp_socket(self):
        """初始化UDP socket，设置超时"""
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.settimeout(5)  # UDP超时5秒
            self.udp_socket.bind((CLIENT_IP, 14301))
        except Exception as e:
            log.error(f"{self.device_type} - UDP socket init failed: {e}")
            raise

    def create_unlock_pack(self, random_num):
        """生成解锁数据包（原逻辑不变，预留扩展）"""
        return self.config["udp_pack_template"]

    def unlock(self):
        """执行解锁操作（优化资源释放）"""
        success = False
        try:
            random_num = format((int(self.random_n, 16) + self.random_index) % 256, '02x')
            udp_pack = self.create_unlock_pack(random_num)
            self.udp_socket.sendto(bytes.fromhex(udp_pack), (self.config["damen_ip"], 14301))
            log.info(f"{self.device_type} - Unlock packet sent: {udp_pack[:30]}...")  # 精简日志
            success = True
        except socket.timeout:
            log.error(f"{self.device_type} - UDP send timeout")
        except Exception as e:
            log.error(f"{self.device_type} - Unlock failed: {e}")
        finally:
            self.random_index += 1
            # 确保UDP socket关闭（即使绑定失败）
            if self.udp_socket:
                self.udp_socket.close()
                self.udp_socket = None
            return success


# ========== TCP连接优化：线程安全+重连策略 ==========
def conn_tcp():
    """线程安全的TCP连接的重连函数"""
    global tcp_client_socket
    with tcp_lock:  # 避免多线程同时重连
        try:
            # 关闭旧连接
            if tcp_client_socket:
                try:
                    tcp_client_socket.shutdown(socket.SHUT_RDWR)
                except:
                    pass
                tcp_client_socket.close()
                tcp_client_socket = None
                log.info("TCP - Closed old connection")

            # 创建新连接
            tcp_client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_client_socket.settimeout(15)  # 加长超时时间（适应网络波动）
            tcp_client_socket.connect(TCP_SERVER)
            tcp_client_socket.settimeout(None)  # 接收数据时取消超时

            # 订阅主题（复用配置，避免重复创建UnlockClient）
            all_topics = ",".join([cfg["topic"] for cfg in device_configs.values()])
            subscribe_cmd = f'cmd=1&uid={UID}&topic={all_topics}\r\n'
            tcp_client_socket.send(subscribe_cmd.encode("utf-8"))
            log.info(f"TCP - Connected successfully, subscribed: {all_topics}")
            return True
        except Exception as e:
            log.error(f"TCP - Connection failed: {e}")
            tcp_client_socket = None
            return False


# ========== 心跳优化：避免重复定时器 ==========
def ping():
    """心跳发送（防止定时器累积）"""

    def ping_task():
        while True:
            time.sleep(30)  # 30秒发送一次
            try:
                with tcp_lock:
                    if tcp_client_socket and tcp_client_socket.fileno() != -1:
                        tcp_client_socket.send(b'ping\r\n')
                        # log.debug("TCP - Ping sent")  # 生产环境可关闭
                    else:
                        log.warning("TCP - Socket not available, reconnecting...")
                        conn_tcp()
            except Exception as e:
                log.error(f"TCP - Ping failed: {e}")
                conn_tcp()

    # 启动独立心跳线程（避免Timer累积）
    ping_thread = threading.Thread(target=ping_task, name="PingThread", daemon=True)
    ping_thread.start()


# ========== 数据接收优化：容错+流量控制 ==========
def recv_data_loop():
    """数据接收循环（增强容错）"""
    topic_to_device = {
        "fxJB63mYW006": DEVICE_DIKU,
        "eCE5rY9Xa006": DEVICE_DONGMEN,
        "bnv7cDLpM006": DEVICE_YILOU
    }

    buffer = b""  # 处理粘包的缓冲区
    while True:
        try:
            # 确保TCP连接有效
            with tcp_lock:
                if not tcp_client_socket or tcp_client_socket.fileno() == -1:
                    log.warning("TCP - Reconnecting...")
                    if not conn_tcp():
                        time.sleep(5)  # 重连失败后等待5秒
                        continue

            # 接收数据（每次最多4096字节，避免内存溢出）
            data = tcp_client_socket.recv(4096)
            if not data:
                log.error("TCP - Connection closed by server")
                conn_tcp()
                time.sleep(2)
                continue

            # 处理粘包（按\r\n分割指令）
            buffer += data
            while b'\r\n' in buffer:
                cmd, buffer = buffer.split(b'\r\n', 1)
                if not cmd:
                    continue
                try:
                    cmd_str = cmd.decode('utf-8', errors='replace').strip()
                    log.info(f"TCP - Received cmd: {cmd_str}")

                    # 匹配设备并处理指令
                    for topic, device_type in topic_to_device.items():
                        if topic in cmd_str:
                            if cmd_str.startswith('cmd=2') and 'msg=on' in cmd_str:
                                handle_device_command(device_type, cmd_str)
                            break
                except Exception as e:
                    log.error(f"TCP - Parse cmd failed: {e}, raw: {cmd.hex()}")

        except socket.error as e:
            log.error(f"TCP - Recv error: {e}")
            conn_tcp()
            time.sleep(5)
        except Exception as e:
            log.error(f"TCP - Recv loop exception: {e}", exc_info=True)
            time.sleep(5)


# ========== 设备指令处理 ==========
def handle_device_command(device_type, cmd_str):
    """处理设备指令（优化线程管理）"""
    log.info(f"Device - Received unlock command for {device_type}")

    # 解锁任务（使用线程池更高效，避免线程爆炸）
    def unlock_task():
        client = UnlockClient(device_type)
        success = client.unlock()
        # 发送响应（仅在解锁成功时）
        if success:
            try:
                topic = device_configs[device_type]["topic"]
                response = f'cmd=2&uid={UID}&topic={topic}&msg=off\r\n'
                with tcp_lock:
                    if tcp_client_socket and tcp_client_socket.fileno() != -1:
                        tcp_client_socket.send(response.encode("utf-8"))
                        log.info(f"Device - Sent response for {device_type}: {response.strip()}")
            except Exception as e:
                log.error(f"Device - Send response failed: {e}")

    # 使用 daemon 线程（避免主线程退出时阻塞）
    thread = threading.Thread(target=unlock_task, name=f"Unlock-{device_type}", daemon=True)
    thread.start()


# ========== 信号处理：优雅退出 ==========
def signal_handler(signum, frame):
    """处理系统信号（如Ctrl+C、kill）"""
    log.info(f"System - Received signal {signum}, exiting gracefully...")
    with tcp_lock:
        if tcp_client_socket:
            try:
                tcp_client_socket.shutdown(socket.SHUT_RDWR)
                tcp_client_socket.close()
            except:
                pass
    log.info("System - Program exited normally")
    os._exit(0)


# ========== 主程序入口 ==========
if __name__ == '__main__':
    # 注册信号处理（优雅退出）
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    log.info("=" * 50)
    log.info("Doubao Device Control Program Started (Orange Pi Zero3 Compatible)")
    log.info("=" * 50)

    # 初始化TCP连接（最多重试5次）
    retry_count = 0
    while retry_count < 5 and not conn_tcp():
        retry_count += 1
        log.info(f"TCP - Retry connection ({retry_count}/5)...")
        time.sleep(3)
    if retry_count >= 5 and not tcp_client_socket:
        log.error("TCP - Failed to connect after 5 retries, exiting...")
        os._exit(1)

    # 启动心跳线程
    ping()

    # 启动数据接收线程（非daemon，确保主线程等待）
    recv_thread = threading.Thread(target=recv_data_loop, name="RecvThread")
    recv_thread.start()

    # 主线程等待接收线程（避免退出）
    recv_thread.join()