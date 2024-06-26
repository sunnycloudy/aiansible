# AIAnsible:
[Link to ENGLISH README](./ENGLISH_README.md)

  调试ansible, 用ai自动注释，自动分析报错，自动给出改进建议。

  Debugging Ansible with AI for automatic commenting, error analysis, and providing suggestions for improvement.

## 技术问答:
qq群: 937374915

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

![Alt text](image-5.png)

如果要设置成英文版:
```
export AIANSIBLE_LANG=EN
```

![Alt text](image-6.png)

### 或在aiansible中用":cn"或":en"命令切换:
![Alt text](image-4.png)

### 推荐环境:
```
(base) root@8fb53c0330bb /home/nujnus/workspace/aiansible ±main # python --version
Python 3.9.18
(base) root@8fb53c0330bb /home/nujnus/workspace/aiansible ±main⚡ # ansible --version
ansible [core 2.12.10]
  config file = None
  configured module search path = ['/root/.ansible/plugins/modules', '/usr/share/ansible/plugins/modules']
  ansible python module location = /opt/conda/lib/python3.9/site-packages/ansible
  ansible collection location = /root/.ansible/collections:/usr/share/ansible/collections
  executable location = /opt/conda/bin/ansible
  python version = 3.9.18 (main, Sep 11 2023, 13:41:44) [GCC 11.2.0]
  jinja version = 3.1.2
  libyaml = True

```

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

- (4) **配置ai参数:**

如果不设置就没有ai提示功能, 但不影响调试功能.

**使用配置文件(推荐)**

创建配置文件位置: ~/.aiansible_plugin/config.yml

```
openai:
  api_key: https://api.moonshot.cn/v1 #或者其他兼容openai的api地址
  api_url: your_openai_api_url_here #或者其他兼容openai的key
  model: moonshot-v1-8k #或者其他兼容openai的model名
```

**或者使用环境变量配置ai**
```
export OPENAI_API_URL=https://api.moonshot.cn/v1  #或者其他兼容openai的api地址
export OPENAI_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx #或者其他兼容openai的key
export OPENAI_MODEL=moonshot-v1-8k #或者其他兼容openai的model名
```


- (5) **运行:**
```
# 在debug.cfg中配置好插件
export ANSIBLE_CONFIG=./debug.cfg
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

**使用配置文件(推荐)**

如果不设置就没有ai提示功能,

创建配置文件位置: ~/.aiansible_plugin/config.yml

```
openai:
  api_key: https://api.moonshot.cn/v1
  api_url: your_openai_api_url_here
  model: moonshot-v1-8k
```

**或者使用环境变量配置ai**

```
export OPENAI_API_URL=https://api.moonshot.cn/v1  #或者其他兼容openai的api地址
export OPENAI_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx #或者其他兼容openai的key
export OPENAI_MODEL=moonshot-v1-8k #或者其他兼容openai的model名
```

**运行**
```
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
