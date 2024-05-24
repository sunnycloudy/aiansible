from setuptools import setup, find_packages
from setuptools.command.install import install

# 自定义安装命令
class CustomInstallCommand(install):
    def run(self):
        install.run(self)
        # 导入post_install.py中的函数
        from scripts.post_install import create_aiansible_plugin_dir
        create_aiansible_plugin_dir()

setup(
    name='aiansible',
    version='1.0',
    packages=find_packages(),
    # 其他参数...
    cmdclass={
        'install': CustomInstallCommand,
    },
)