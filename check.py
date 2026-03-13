# check_env.py
import sys

print(f"当前使用的 Python 解释器路径: {sys.executable}")
print(f"Python 版本: {sys.version}\n")

libraries = ['torch', 'numpy', 'scipy']
for lib in libraries:
    try:
        module = __import__(lib)
        print(f"[OK] 已安装: {lib} (版本: {module.__version__})")
    except ImportError:
        print(f"[警告] 缺失依赖: {lib}")