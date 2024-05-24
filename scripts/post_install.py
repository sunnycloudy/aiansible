import os
import sys

def create_aiansible_plugin_dir():
    # 获取用户的主目录
    home_dir = os.path.expanduser('~')
    # 创建.aiansible_plugin目录
    plugin_dir = os.path.join(home_dir, '.aiansible_plugin')
    if not os.path.exists(plugin_dir):
        os.makedirs(plugin_dir)
        print(f"Created directory: {plugin_dir}")
    else:
        print(f"Directory already exists: {plugin_dir}")
    # 复制文件到.aiansible_plugin目录
    # 假设要复制的文件位于your_package/files目录下
    files_to_copy = ['aiansible.py']
    for file_name in files_to_copy:
        src_file = os.path.join('plugins', file_name)
        dst_file = os.path.join(plugin_dir, file_name)
        with open(src_file, 'r') as src, open(dst_file, 'w') as dst:
            dst.write(src.read())
        print(f"Copied {file_name} to {plugin_dir}")

if __name__ == "__main__":
    create_aiansible_plugin_dir()