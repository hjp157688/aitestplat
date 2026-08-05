from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
import shutil
import subprocess
import platform
import os
import json
import logging

logger = logging.getLogger(__name__)

class EnvironmentConfigViewSet(viewsets.ViewSet):
    """
    UI自动化环境配置视图集
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def check_environment(self, request):
        """
        检测环境状态 (系统浏览器和Playwright浏览器)
        """
        import sys
        
        # 1. 检测系统浏览器 (Selenium常用)
        system_browsers_list = ['chrome', 'firefox', 'edge'] # Safari not on Windows usually
        if platform.system() == 'Darwin':
             system_browsers_list.append('safari')
             
        system_results = []

        is_windows = platform.system() == 'Windows'

        for browser in system_browsers_list:
            installed = False
            version = None
            install_cmd = ""
            
            if browser == 'chrome':
                if is_windows:
                    paths = [
                        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe")
                    ]
                    for p in paths:
                        if os.path.exists(p):
                            installed = True
                            break
                    install_cmd = "请下载 Chrome 安装包安装"
                elif platform.system() == 'Darwin':  # macOS
                    if os.path.exists('/Applications/Google Chrome.app'):
                        installed = True
                    install_cmd = "brew install --cask google-chrome"
                else:  # Linux
                    chrome_paths = [
                        '/usr/bin/google-chrome',
                        '/usr/bin/google-chrome-stable',
                        '/usr/bin/chromium-browser',
                        '/usr/bin/chromium',
                        '/opt/google/chrome/google-chrome',
                        '/snap/bin/chromium'
                    ]
                    for path in chrome_paths:
                        if os.path.exists(path):
                            installed = True
                            break
                    install_cmd = "sudo dnf install chromium 或 sudo dnf install google-chrome-stable"
                    
            elif browser == 'firefox':
                if is_windows:
                    paths = [
                        r"C:\Program Files\Mozilla Firefox\firefox.exe",
                        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe"
                    ]
                    for p in paths:
                        if os.path.exists(p):
                            installed = True
                            break
                    install_cmd = "请下载 Firefox 安装包安装"
                elif platform.system() == 'Darwin':  # macOS
                    if os.path.exists('/Applications/Firefox.app'):
                        installed = True
                    install_cmd = "brew install --cask firefox"
                else:  # Linux
                    firefox_paths = [
                        '/usr/bin/firefox',
                        '/usr/bin/firefox-esr'
                    ]
                    for path in firefox_paths:
                        if os.path.exists(path):
                            installed = True
                            break
                    install_cmd = "sudo dnf install firefox"
                    
            elif browser == 'safari':
                if not is_windows and os.path.exists('/Applications/Safari.app'):
                    installed = True
                install_cmd = "系统自带"
                
            elif browser == 'edge':
                if is_windows:
                    paths = [
                         r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                         r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
                    ]
                    for p in paths:
                        if os.path.exists(p):
                            installed = True
                            break
                    install_cmd = "请下载 Edge 安装包安装"
                elif platform.system() == 'Darwin':  # macOS
                    if os.path.exists('/Applications/Microsoft Edge.app'):
                        installed = True
                    install_cmd = "brew install --cask microsoft-edge"
                else:  # Linux
                    edge_paths = [
                        '/usr/bin/microsoft-edge',
                        '/usr/bin/microsoft-edge-stable',
                        '/opt/microsoft/msedge/msedge'
                    ]
                    for path in edge_paths:
                        if os.path.exists(path):
                            installed = True
                            break
                    install_cmd = "从微软官网下载 Edge Linux 版本安装包"

            system_results.append({
                'name': browser,
                'installed': installed,
                'version': version, # Version check omitted for simplicity/performance
                'install_cmd': install_cmd
            })

        # 2. 检测Playwright浏览器
        playwright_browsers_list = ['chromium', 'firefox', 'webkit']
        playwright_results = []
        
        # Playwright 缓存路径
        if is_windows:
            playwright_cache_dir = os.path.join(os.environ.get('LOCALAPPDATA'), 'ms-playwright')
        elif platform.system() == 'Darwin':  # macOS
            playwright_cache_dir = os.path.expanduser('~/Library/Caches/ms-playwright')
        else:  # Linux
            playwright_cache_dir = os.path.expanduser('~/.cache/ms-playwright')
        
        # 调试信息：打印缓存路径
        print(f"Playwright cache dir: {playwright_cache_dir}")

        for browser in playwright_browsers_list:
            installed = False
            version = None
            install_cmd = f"playwright install {browser}"
            
            # 检查缓存目录中是否有对应的浏览器文件夹
            if os.path.exists(playwright_cache_dir):
                for dirname in os.listdir(playwright_cache_dir):
                    # 匹配规则: chromium-123456, firefox-1234, webkit-1234
                    # 注意: 有时候是 chromium-vxxxx
                    if dirname.startswith(browser + '-'):
                        installed = True
                        version = dirname.split('-')[-1]
                        break
            
            playwright_results.append({
                'name': browser,
                'installed': installed,
                'version': version,
                'install_cmd': install_cmd
            })

        return Response({
            'os': platform.system(),
            'system_browsers': system_results,
            'playwright_browsers': playwright_results
        })

    @action(detail=False, methods=['post'])
    def install_driver(self, request):
        """
        安装浏览器驱动
        """
        browser = request.data.get('browser')
        if not browser:
            return Response({'error': 'Browser name is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 使用当前 Python 环境执行模块安装命令
            import sys
            subprocess.run([sys.executable, '-m', 'playwright', 'install', browser], check=True)
            return Response({'message': f'Successfully installed driver for {browser}'})
        except subprocess.CalledProcessError as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


