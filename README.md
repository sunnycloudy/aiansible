# aiansible:
[Link to ENGLISH README](./ENGLISH_README.md)


  调试ansible, 并通过chatgpt or kimi注释和提示错误的解决办法.

  Debug Ansible, and use chatgpt or kimi AI annotations and hints to resolve errors.

## 基本使用说明/basic usage:
```
:cn            设置语言为中文
:en            设置语言为英文
i              对当前执行的任务代码进行注释
ir             对当前执行的任务代码进行注释, 再分析一下运行结果, 再给出改进建议
ask            请根据当前ansible任务:回答问题
n    next      运行下一个任务
m              不再在紧接着的同一个任务处停留
c    continue  继续运行直到下一个断点
b              创建断点
p              查看已经创建的断点
d    delete    删除断点
bt             查看已经运行过哪些任务了
code           查看正在运行的任务的代码
v              用vscode打开对应文件
a    arg       查看所有参数, 或单个参数 (在任务没有被skipped的前提下)
?    help      查看使用说明
exit           退出
```
### 查看当前任务的运行结果:
```
Aiansible(CN) => result._result
{'msg': 'Check roles/kubespray-defaults/defaults/main.yml', '_ansible_verbose_always': True, '_ansible_no_log': False, 'changed': False}
```

## ai提示效果/example:
默认是中文版,中文版效果: 
![Alt text](image-2.png)
如果要设置成英文版:
```
export AIANSIBLE_LANG=EN
```
![Alt text](image-3.png)

### 或在aiansible中用":cn"或":en"命令切换:
![Alt text](image-4.png)


### 安装并开始使用 :
- (1) **下载和安装:**
```
  git clone https://github.com/sunnycloudy/aiansible.git
  cd aiansible
  pip install .  #=> 会生成插件目录: ~/.aiansible_plugin
```

- (2) **安装依赖:**
```
pip install  -r requirements.txt
```

- (3) **创建一个:debug.cfg**
```
[defaults]
callback_plugins = ~/.aiansible_plugin
callbacks_enabled = aiansible.py
```
- (4) **设置环境变量:**
```
# 可选的两个变量, 如果不设置就没有ai提示功能, 但依然能调试.
export OPENAI_API_URL=https://api.moonshot.cn/v1  #或者其他兼容openai的api地址
export OPENAI_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx #或者其他兼容openai的key

# 在debug.cfg中配置好插件
export ANSIBLE_CONFIG=./debug.cfg
```
- (5) **运行命令/run command:**
```
ansible-playbook  xxx_playbook.yml
```

---
# demo:

## 以调试kubespray为例:
```
# 先找到
kubespray/ansible.cfg
```

### 更改kubespray默认配置:
```
[ssh_connection]
pipelining=True
ansible_ssh_args = -o ControlMaster=auto -o ControlPersist=30m -o ConnectionAttempts=100 -o UserKnownHostsFile=/dev/null
#control_path = ~/.ssh/ansible-%%r@%%h:%%p
[defaults]
# https://github.com/ansible/ansible/issues/56930 (to ignore group names with - and .)
force_valid_group_names = ignore

host_key_checking=False
gathering = smart
fact_caching = jsonfile
fact_caching_connection = /tmp
fact_caching_timeout = 86400
stdout_callback = default
display_skipped_hosts = no
library = ./library
# callbacks_enabled = profile_tasks,ara_default      #<= 注释掉   (･ω･)ﾉ
callback_plugins = ~/.aiansible_plugin               #<=  新添加的 (｡･ω･｡)ﾉ
callbacks_enabled = aiansible.py                     #<=  新添加的 ( ・ω・ )ノ

roles_path = roles:$VIRTUAL_ENV/usr/local/share/kubespray/roles:$VIRTUAL_ENV/usr/local/share/ansible/roles:/usr/share/kubespray/roles
deprecation_warnings=False
inventory_ignore_extensions = ~, .orig, .bak, .ini, .cfg, .retry, .pyc, .pyo, .creds, .gpg
[inventory]
ignore_patterns = artifacts, credentials

```

### 运行命令/run command:
```
# 如果不设置就没有ai提示功能, 但依然能调试.
export OPENAI_API_URL=https://api.moonshot.cn/v1  #或者其他兼容openai的api地址
export OPENAI_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx #或者其他兼容openai的key

# 开始调试:
export ANSIBLE_CONFIG=./ansible.cfg
ansible-playbook  --become  -i  inventory/mycluster/inventory.ini  cluster.yml
```
![Alt text](image-1.png)


### 编辑模式:emacs模式和支持vim模式, 默认为emacs模式
```
export AIANSIBLE_EDITMODE=vi
#或
export AIANSIBLE_EDITMODE=emacs
```
