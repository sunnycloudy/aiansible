# aiansible:
[切换到中文](./README.md)

  调试ansible, 并通过chatgpt or kimi注释和提示错误的解决办法.

  Debug Ansible, and use chatgpt or kimi AI annotations and hints to resolve errors.
  
  - "It may be the first non-embedded Ansible debugger on the market."
  - "It should be the first Ansible debugger on the market with AI hinting features."
  - "It may be the second Ansible debugger on the market that truly provides breakpoint debugging capabilities."


## 基本使用说明/basic usage:
```
:cn            Set the language to Chinese
:en            Set the language to English
i              Annotate the code of the currently executing task
ir             Annotate the code of the currently executing task, analyze the results, and provide suggestions for improvement
ask            Please answer questions based on the current Ansible task
n    next      Run the next task
m              Do not stay at the same task again immediately
c    continue  Continue running until the next breakpoint
b              Create a breakpoint
p              View created breakpoints
d    delete    Delete a breakpoint
bt             View which tasks have been run
code           View the code of the currently running task
v              Open the corresponding file with VSCode
a    arg       View all arguments, or a single argument (assuming the task has not been skipped)
?    help      View the usage instructions
exit           Exit
```

### check the result of current ansible task:
```
Aiansible(CN) => result._result
{'msg': 'Check roles/kubespray-defaults/defaults/main.yml', '_ansible_verbose_always': True, '_ansible_no_log': False, 'changed': False}
```


## ai prompt example:
If you want to use English:
```
export AIANSIBLE_LANG=EN
```
![Alt text](image-3.png)

### or use ":cn"and":en" to switch language:
![Alt text](image-4.png)



### install and start using aiansible:
- (1) **download and install**
```
  git clone https://github.com/sunnycloudy/aiansible.git
  cd aiansible
  pip install .  #=> will generate dir: ~/.aiansible_plugin
```


- (2) **install dependents:**
```
pip install  -r requirements.txt
```

- (3) **create a:debug.cfg**
```
[defaults]
callback_plugins = ~/.aiansible_plugin
callbacks_enabled = aiansible.py
```
- (4) **set environments:**
```
# If it's not necessary to use AI, you can choose not to set following variable:
export OPENAI_API_URL=https://api.moonshot.cn/v1  #Or other API addresses compatible with OpenAI.
export OPENAI_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx #Or other keys compatible with OpenAI.

# Configure the plugin in the debug.cfg file.
export ANSIBLE_CONFIG=./debug.cfg
```
- (5) **run command:**
```
ansible-playbook  xxx_playbook.yml
```
---
# demo:

## kubespray example:
```
# find
kubespray/ansible.cfg
```

### edit kubespray default ansible.cfg:
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
# callbacks_enabled = profile_tasks,ara_default      #<= comment it   (･ω･)ﾉ
callback_plugins = ~/.aiansible_plugin               #<=  new line (｡･ω･｡)ﾉ
callbacks_enabled = aiansible.py                     #<=  new line ( ・ω・ )ノ

roles_path = roles:$VIRTUAL_ENV/usr/local/share/kubespray/roles:$VIRTUAL_ENV/usr/local/share/ansible/roles:/usr/share/kubespray/roles
deprecation_warnings=False
inventory_ignore_extensions = ~, .orig, .bak, .ini, .cfg, .retry, .pyc, .pyo, .creds, .gpg
[inventory]
ignore_patterns = artifacts, credentials

```

### run command:

```
# If it's not necessary to use AI, you can choose not to set following variable:
export OPENAI_API_URL=https://api.moonshot.cn/v1  #Or other API addresses compatible with OpenAI.
export OPENAI_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx #Or other keys compatible with OpenAI.

# run playbook in debug mode:
export AIANSIBLE_LANG=EN
export ANSIBLE_CONFIG=./ansible.cfg
ansible-playbook  --become  -i  inventory/mycluster/inventory.ini  cluster.yml
```
![Alt text](image-1.png)

### edit mode:support emacs-mode or vim-mode, default is emacs-mode
```
export AIANSIBLE_EDITMODE=vi
#或
export AIANSIBLE_EDITMODE=emacs
```