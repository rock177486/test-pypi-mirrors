import urllib.request
import re
import time
import urllib.parse
from html.parser import HTMLParser
from packaging.utils import parse_wheel_filename, parse_sdist_filename
from packaging.version import Version

# ================= 配置区 =================
TEST_PACKAGE = 'tensorflow'
REPEAT_CNT = 1
DOWNLOAD_TIMEOUT = 5  # 下载测试时长（秒）
CHUNK_SIZE = 1024 * 1024  # 1MB，避免高速网络下循环开销影响测速
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

# ================= 工具函数 =================
def normalize_package_name(name):
    """PEP 503 包名规范化 (防止大写或下划线导致404)"""
    return re.sub(r"[-_.]+", "-", name).lower()

class PyPILinkParser(HTMLParser):
    """健壮地解析 PEP 503 Simple API 的 HTML"""
    def __init__(self):
        super().__init__()
        self.links = []
        self.current_href = None
        
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for name, value in attrs:
                if name == 'href':
                    self.current_href = value
                    break
                    
    def handle_data(self, data):
        if self.current_href and data.strip():
            self.links.append((self.current_href, data.strip()))
            self.current_href = None

def get_display_width(s):
    """计算字符串在终端的实际显示宽度（解决中英文混排对齐问题）"""
    width = 0
    for char in str(s):
        if '\u4e00' <= char <= '\u9fa5':
            width += 2
        else:
            width += 1
    return width

def pad_string(s, width):
    """根据显示宽度填充空格"""
    return str(s) + ' ' * max(0, width - get_display_width(s))

# ================= 核心测速逻辑 =================
def get_mirror_benchmark(simple_url, package_name):
    norm_name = normalize_package_name(package_name)
    pypi_url = f'{simple_url}/{norm_name}/'
    
    req = urllib.request.Request(pypi_url, headers={'User-Agent': USER_AGENT})
    
    # 1. 测试列表响应时间
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.getcode() == 200
        response_html = resp.read().decode('utf-8', errors='ignore')
    t1 = time.perf_counter()
    listing_speed = f'{1000*(t1-t0):.0f}ms'

    # 2. 解析 HTML 提取链接并寻找最新稳定版
    parser = PyPILinkParser()
    parser.feed(response_html)
    
    files_by_version = {}
    for href, filename in parser.links:
        try:
            if filename.endswith('.whl'):
                name, version, build, tags = parse_wheel_filename(filename)
            elif filename.endswith('.tar.gz') or filename.endswith('.zip'):
                name, version = parse_sdist_filename(filename)
            else:
                continue
            
            if not isinstance(version, Version) or version.is_prerelease or version.is_devrelease:
                continue
                
            files_by_version.setdefault(version, []).append((filename, href))
        except Exception:
            continue

    if not files_by_version:
        raise ValueError("未找到有效稳定版")
        
    latest_version = max(files_by_version.keys())
    latest_files = files_by_version[latest_version]
    
    wheel_files = [f for f in latest_files if f[0].endswith('.whl')]
    download_filename, download_href = wheel_files[0] if wheel_files else latest_files[0]

    # 3. 测试下载速度
    package_url = urllib.parse.urljoin(pypi_url, download_href)
    req_dl = urllib.request.Request(package_url, headers={'User-Agent': USER_AGENT})
    
    t0 = time.perf_counter()
    file_size = 0
    with urllib.request.urlopen(req_dl, timeout=15) as resp:
        assert resp.getcode() == 200
        while True:
            chunk = resp.read(CHUNK_SIZE)
            if not chunk:
                break
            file_size += len(chunk)
            t1 = time.perf_counter()
            if t1 - t0 > DOWNLOAD_TIMEOUT:
                break
                
    duration = t1 - t0 if (t1 - t0) > 0 else 0.001
    speed_val = file_size / duration / 1024 / 1024  # 原始浮点数，用于排序
    download_speed = f'{speed_val:.2f}MB/s'

    # 返回4个值，新增 speed_val
    return str(latest_version), listing_speed, download_speed, speed_val

# ================= 主程序 =================
if __name__ == '__main__':
    raw_data = '''
阿里云 https://mirrors.aliyun.com/pypi/simple
腾讯云 https://mirrors.cloud.tencent.com/pypi/simple
华为云 https://mirrors.huaweicloud.com/repository/pypi/simple
清华大学 https://pypi.tuna.tsinghua.edu.cn/simple
中国科学技术大学 https://mirrors.ustc.edu.cn/pypi/simple
北京外国语大学 https://mirrors.bfsu.edu.cn/pypi/web/simple
上海交通大学 https://mirror.sjtu.edu.cn/pypi/web/simple
北京大学 https://mirrors.pku.edu.cn/pypi/web/simple
南京工业大学 https://mirrors.njtech.edu.cn/pypi/web/simple
浙江大学 https://mirrors.zju.edu.cn/pypi/web/simple
PyPI 官网 https://pypi.org/simple
    '''
    
    mirrors = []
    for line in raw_data.strip().splitlines():
        parts = line.strip().split()
        if len(parts) >= 2:
            mirrors.append((parts[0], parts[-1]))

    headers = ['镜像站名称', '最新稳定版', '列表耗时', '下载速度']
    widths = [20, 15, 12, 15]
    
    print("开始测速，请稍候... (需遍历所有镜像并下载文件)\n")
    
    results = []
    # 1. 收集所有结果
    for site_name, simple_url in mirrors:
        simple_url = simple_url.rstrip('/')
        try:
            ver, list_spd, dl_spd, speed_val = get_mirror_benchmark(simple_url, TEST_PACKAGE)
            results.append({
                'name': site_name, 'version': ver, 
                'list_speed': list_spd, 'dl_speed': dl_spd, 
                'speed_val': speed_val
            })
        except KeyboardInterrupt:
            raise
        except Exception as e:
            # 失败的镜像站速度记为 -1，自动沉底
            results.append({
                'name': site_name, 'version': 'Error', 
                'list_speed': '-', 'dl_speed': 'Failed', 
                'speed_val': -1.0
            })

    # 2. 按下载速度从大到小排序
    results.sort(key=lambda x: x['speed_val'], reverse=True)

    # 3. 统一打印表格
    print(''.join(pad_string(h, w) for h, w in zip(headers, widths)))
    print('-' * sum(widths))
    
    for r in results:
        row = [r['name'], r['version'], r['list_speed'], r['dl_speed']]
        print(''.join(pad_string(c, w) for c, w in zip(row, widths)))