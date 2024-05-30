import os
import sys
from ansible.plugins.callback import CallbackBase
from ansible import constants as C
import json
import tempfile
import subprocess
from io import StringIO
from contextlib import redirect_stdout
from prompt_toolkit import prompt
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit import PromptSession
from prompt_toolkit.enums import EditingMode
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys


import re
import json

import yaml
from openai import OpenAI
import re

ASK_AI_TO_COMMENT = 0
ASK_AI_TO_ANALYZE = 1
ASK_AI_TO_CHAT = 2

GREEN = "\033[92m"
RED = "\033[91m"
BLUE = "\033[34m"
YELLOW = "\033[93m"
RESET = "\033[0m"
HELP = """
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
"""

ENGLISH_HELP = """
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
"""


def colorize_code(code):
    # 正则表达式匹配以 # 开头的单行注释
    comment_pattern = r"(#.*)"

    # 使用黄色替换注释部分
    colored_code = re.sub(
        comment_pattern, lambda match: YELLOW + match.group(0) + RESET, code
    )

    ## 将剩余的代码部分包装在绿色中
    # colored_code = re.sub(
    #    r"(.*\n)", lambda match: GREEN + match.group(0) + RESET, colored_code
    # )

    # 如果提供了特殊字符串和颜色代码，则替换该字符串为指定颜色
    special_string_list = [
        "代码和注释",
        "运行结果分析",
        "改进建议",
        "code and comment",
        "Analysis of the results",
        "Improvements",
    ]
    for special_string in special_string_list:
        special_string_pattern = re.escape(special_string)  # 转义特殊字符
        colored_code = re.sub(
            special_string_pattern,
            lambda match: GREEN + match.group(0) + RESET,
            colored_code,
            flags=re.IGNORECASE,
        )

    return colored_code


def is_natural_number(input_str):
    try:
        pattern = r"^\d+$"
        match = re.match(pattern, input_str)
        return match is not None
    except Exception as e:
        print(f"An error occurred: {e}")


def get_env_variable_or_default(env_name, default_value):
    # 使用 os.environ.get 方法获取环境变量的值
    # 如果环境变量不存在，返回 default_value
    return os.environ.get(env_name, default_value)


def print_error(message):
    # ANSI红色代码
    RED = "\033[91m"
    # ANSI重置代码，用于重置文本颜色
    RESET = "\033[0m"

    # 打印错误消息，使用红色高亮
    print(f"{RED}{message}{RESET}")


def load_config():
    # 构建配置文件的路径
    config_path = os.path.join(
        os.path.expanduser("~"), ".aiansible_plugin", "config.yml"
    )

    # 检查配置文件是否存在
    if not os.path.exists(config_path):
        print_error(f"error: Configuration file not found: {config_path}")
        return {}
    else:
        # 读取并解析YAML配置文件
        with open(config_path, "r") as file:
            config = yaml.safe_load(file)

        if not isinstance(config, dict):
            print_error(f"error: config must be a dictionary: {config_path}")
            return {}

        # 返回配置
        return config


class CallbackModule(CallbackBase):

    history = InMemoryHistory()

    def __init__(self, display=None, options=None):
        super().__init__(display=display, options=options)
        self.nujnus_task_path_list = []
        # 读取断点清单文件
        self.break_list_file_path = os.environ.get("BREAK_LIST_FILE_PATH")
        self.AIANSIBLE_EDITMODE = os.environ.get("AIANSIBLE_EDITMODE")
        self.aiansible_lang = os.environ.get("AIANSIBLE_LANG")
        if not self.aiansible_lang:
            self.aiansible_lang = "CN"
        if not self.break_list_file_path:
            self.break_list_file_path = "./breaklist.yml"
        self.output_point_list_file_path = os.environ.get("OUTPUT_POINT_LIST_FILE_PATH")
        if not self.output_point_list_file_path:
            self.output_point_list_file_path = "./output_list.yml"
        self.output_file_path = os.environ.get("OUTPUT_FILE_PATH")
        if not self.output_file_path:
            self.output_file_path = "./output.txt"
        self.result_history = []
        self.break_list = []
        self.output_list = []
        self.get_break_list()
        self.get_output_list()
        # 继续运行标志
        self.continue_flag = False
        # 记录要跳过的同名的任务
        self.move_on_at_task = None

        config = load_config()
        openai_config = config.get("openai", {})
        api_key = os.environ.get("OPENAI_API_KEY", default=openai_config.get("api_key"))
        base_url = os.environ.get(
            "OPENAI_API_URL", default=openai_config.get("api_url")
        )
        self.ai_model = os.environ.get(
            "OPENAI_MODEL", default=openai_config.get("model")
        )
        if api_key == None:
            print_error("error: ai api_key is None")
        if base_url == None:
            print_error("error: ai base_url is None")
        if self.ai_model == None:
            print_error("error: ai model is None")
        if api_key == None or base_url == None or self.ai_model == None:
            self.enable_ai = False
        else:
            self.enable_ai = True
            self.ai_client = OpenAI(api_key=api_key, base_url=base_url)
            self.chat_context = {
                "role": "system",
                "content": "你是 commentator，你更擅长中文和英文的对话。你会为用户提供安全，有帮助，准确的回答。",  # 你会根据用户给出的代码, 在用户给出的代码之后写出用中文进行的注释, 你会将用户给出的代码 和你的注释合并在一起.
            }

            self.chat_history = []
            self.chat_history.append(self.chat_context)

    def get_comment_prompt(self):

        type_prompt = """\n请返回类似如下格式的回复:
[代码和注释:]
11|    - name: "Check {{ minimal_ansible_version }} <= Ansible version < {{ maximal_ansible_version }}"  # 任务名称，用于检查Ansible的版本是否在指定的范围内
12|      assert:  # 断言模块，用于验证条件是否为真
13|        msg: "Ansible must be between {{ minimal_ansible_version }} and {{ maximal_ansible_version }} exclusive"  # 如果断言失败，将显示此消息
14|        that:  # 指定断言的条件
15|          - ansible_version.string is version(minimal_ansible_version, ">=")  # 条件1：Ansible版本至少为minimal_ansible_version
16|          - ansible_version.string is version(maximal_ansible_version, "<")  # 条件2：Ansible版本小于maximal_ansible_version
17|      tags:  # 标签，用于选择执行哪些任务
18|        - check  # 给该任务添加的标签为check
"""

        en_type_prompt = """\n请返回类似如下格式的回复:
[ code and comment: ]
11|    - name: "Check {{ minimal_ansible_version }} <= Ansible version < {{ maximal_ansible_version }}" # This task is named to check if the Ansible version is between the specified minimum and maximum exclusive versions.
12|      assert: # The assert module is used here to ensure that certain conditions are met.
13|        msg: "Ansible must be between {{ minimal_ansible_version }} and {{ maximal_ansible_version }} exclusive" # The message that will be displayed if the assertions fail, indicating the required version range.
14|        that: # The conditions that must be true for the assertions to pass.
15|          - ansible_version.string is version(minimal_ansible_version, ">=") # The first condition checks if the Ansible version is greater than or equal to the minimal version.
16|          - ansible_version.string is version(maximal_ansible_version, "<") # The second condition checks if the Ansible version is less than the maximal version.
17|      tags: # Tags are used to categorize tasks, which can be useful for selective execution.
18|        - check # The task is tagged with 'check', which can be used to run only this task or a group of tasks with this tag.
"""

        if self.aiansible_lang == "CN":
            return (
                "用中文, 在每行代码后的同一行内, 注释一下如下代码(注意:除此之外,不需要额外说明 ):",
                type_prompt,
            )
        elif self.aiansible_lang == "EN":
            return (
                "用英文, 在每行代码后的同一行内, 注释一下如下代码(注意:除此之外,不需要额外说明 ):",
                en_type_prompt,
            )
            # return "In English, maintain the original format and line numbers of the code, show the code, and add comments after each line of code.  (Note: No additional explanation is needed except for this):"
        else:
            return (
                "用中文, 在每行代码后的同一行内, 注释一下如下代码(注意:除此之外,不需要额外说明 ):",
                type_prompt,
            )

    def get_ask_prompt(self):

        if self.aiansible_lang == "CN":
            return "请根据当前ansible任务:", "回答如下问题:"
        elif self.aiansible_lang == "EN":
            return "请根据当前ansible任务:", "用英语回答如下问题:"
        else:
            return "请根据当前ansible任务:", "回答如下问题:"

    def get_result_prompt(self):
        type_prompt = """\n请返回类似如下格式的回复:
[代码和注释:]
11|    - name: "Check {{ minimal_ansible_version }} <= Ansible version < {{ maximal_ansible_version }}"  # 任务名称，用于检查Ansible的版本是否在指定的范围内
12|      assert:  # 断言模块，用于验证条件是否为真
13|        msg: "Ansible must be between {{ minimal_ansible_version }} and {{ maximal_ansible_version }} exclusive"  # 如果断言失败，将显示此消息
14|        that:  # 指定断言的条件
15|          - ansible_version.string is version(minimal_ansible_version, ">=")  # 条件1：Ansible版本至少为minimal_ansible_version
16|          - ansible_version.string is version(maximal_ansible_version, "<")  # 条件2：Ansible版本小于maximal_ansible_version
17|      tags:  # 标签，用于选择执行哪些任务
18|        - check  # 给该任务添加的标签为check

[运行结果分析:] 
- {'_ansible_verbose_always': True, 'changed': False, 'msg': 'All assertions passed', '_ansible_no_log': False}
  - _ansible_verbose_always: True 表示该任务的输出总是以详细模式显示
  - changed: False 表示任务没有改变任何状态或数据
  - msg: 'All assertions passed' 表示所有的断言都通过了，即Ansible版本符合条件
  - _ansible_no_log: False 表示该任务的输出可以被记录

[改进建议：]
- 如果需要在Ansible版本不符合条件时中断执行，可以添加 `fail: yes` 来在断言失败时终止任务。
- 如果需要更详细的错误信息，可以在 `msg` 字段中提供更具体的错误提示。
- 如果`minimal_ansible_version`和`maximal_ansible_version`是动态的，确保它们在运行此任务之前被正确定义和传递。
- 考虑使用 `when` 条件来避免在不需要时执行此任务，例如只在某些特定情况下检查版本。
"""

        en_type_prompt = """\n请返回类似如下格式的回复:
[ code and comment: ]
11|    - name: "Check {{ minimal_ansible_version }} <= Ansible version < {{ maximal_ansible_version }}" # This task is named to check if the Ansible version is between the specified minimum and maximum exclusive versions.
12|      assert: # The assert module is used here to ensure that certain conditions are met.
13|        msg: "Ansible must be between {{ minimal_ansible_version }} and {{ maximal_ansible_version }} exclusive" # The message that will be displayed if the assertions fail, indicating the required version range.
14|        that: # The conditions that must be true for the assertions to pass.
15|          - ansible_version.string is version(minimal_ansible_version, ">=") # The first condition checks if the Ansible version is greater than or equal to the minimal version.
16|          - ansible_version.string is version(maximal_ansible_version, "<") # The second condition checks if the Ansible version is less than the maximal version.
17|      tags: # Tags are used to categorize tasks, which can be useful for selective execution.
18|        - check # The task is tagged with 'check', which can be used to run only this task or a group of tasks with this tag.

[ Analysis of the results: ]
- The task's result indicates that all assertions passed, which means the Ansible version is within the specified range.
- The 'changed' flag is False, which indicates that no changes were made to the system as a result of this task.
- The 'msg' field confirms that all assertions were successful.
- The '_ansible_verbose_always' is True, which means the task's output is displayed in verbose mode.
- The '_ansible_no_log' is False, which means the task's output is logged.

[ Improvements: ]
- If the task should fail and halt the playbook execution when the Ansible version is not within the specified range, you can add a `fail` statement to the assert module.
- To provide more context in the event of a failure, consider enhancing the `msg` with more detailed information.
- Ensure that the variables `minimal_ansible_version` and `maximal_ansible_version` are properly defined and passed into the playbook before this task is executed.
- Use the `when` condition to skip this task when it's not necessary, for example, if the version check is only required under certain conditions.
"""

        if self.aiansible_lang == "CN":
            return (
                "用中文, 在每行代码后的同一行内, 注释一下如下代码, 再分析一下运行结果的原因, 再告诉我该如何改进(注意:除此之外,不需要额外说明 ):",
                "\n运行结果为:",
                type_prompt,
            )
        elif self.aiansible_lang == "EN":
            return (
                "用英文, 在每行代码后的同一行内, 注释一下如下代码, 再分析一下运行结果的原因, 再告诉我该如何改进(注意:除此之外,不需要额外说明 ):",
                "\n运行结果为:",
                en_type_prompt,
            )
        else:
            return (
                "用中文, 在每行代码后的同一行内, 注释一下如下代码, 再分析一下运行结果的原因, 再告诉我该如何改进(注意:除此之外,不需要额外说明 ):",
                "\n运行结果为:",
                type_prompt,
            )

    def chat(self, query, history):
        self.chat_history.append({"role": "user", "content": query})
        completion = self.ai_client.chat.completions.create(
            model=self.ai_model,
            messages=history,
            temperature=0.3,
        )
        result = completion.choices[0].message.content
        history.append({"role": "assistant", "content": result})
        return result

    def get_break_list(self):

        if os.path.exists(self.break_list_file_path):
            # 打开并读取YAML文件
            with open(self.break_list_file_path, "r") as file:
                self.break_list = yaml.safe_load(file)
                if self.break_list == None:
                    self.break_list = []

    def get_output_list(self):

        if os.path.exists(self.output_point_list_file_path):
            # 打开并读取YAML文件
            with open(self.output_point_list_file_path, "r") as file:
                self.output_list = yaml.safe_load(file)
                if self.output_list == None:
                    self.output_list = []

    def save_to_output_list(self, pathspec):
        # 写入break_list文件
        self.output_list.append(pathspec)
        # 打开并读取YAML文件
        with open(self.output_point_list_file_path, "w") as file:
            yaml.dump(self.output_list, file)

    def delete_one_output_point(self, index):
        if len(self.output_list) - 1 >= index:
            self.output_list.pop(index)
            with open(self.output_point_list_file_path, "w") as file:
                yaml.dump(self.output_list, file)

    def check_output_point(self):
        _, _, pathspec = self.get_path(self.nujnus_task)
        if pathspec in self.output_list:
            return True
        return False

    def append_result_to_file_with_path_check(self, file_path, result):
        # 确保目录存在，如果不存在则创建
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # 打开文件并追加内容
        try:
            with open(file_path, "a") as file:
                for key, value in result._task_fields["args"].items():
                    file.write(f"{key}: {value}\n")
                file.write("\n")
            print(f"Content successfully appended to {file_path}")
        except Exception as e:
            print(f"An error occurred: {e}")

    def save_to_break_list(self, pathspec):
        # 写入break_list文件
        self.break_list.append(pathspec)
        # 打开并读取YAML文件
        with open(self.break_list_file_path, "w") as file:
            yaml.dump(self.break_list, file)

    def delete_one_break(self, index):
        if len(self.break_list) - 1 >= index:
            self.break_list.pop(index)
            with open(self.break_list_file_path, "w") as file:
                yaml.dump(self.break_list, file)

    # 读取文件内容的函数
    def read_code_from_file(self, file_path, start_line):
        lines = []
        line_number = 0
        start_line -= 1

        try:
            with open(file_path, "r") as file:
                for line in file:
                    if line_number >= start_line:
                        if line.strip() == "":
                            break  # 遇到空行，停止收集
                        # 达到启始行, 开始收集
                        lines.append((line_number, line))
                    line_number += 1
                    continue  # 跳过起始行之前的行

        except FileNotFoundError:
            print("File not found.")
            return None
        except Exception as e:
            print(f"An error occurred: {e}")
            return None

        return lines

    # 打印行的函数
    def print_lines(self, lines, color=None):
        if lines is None:
            return

        for line in lines:
            # 这里可以添加行号信息，如果需要的话
            self.display_line(line, color)

    # 显示单行的函数
    def display_line(self, line, color=None):
        # 这里可以是任何显示逻辑，例如打印到控制台或显示在GUI界面
        print(line, end="")

    # 打印代码的函数，它调用read_code_from_file并使用print_lines打印结果
    # print_code
    def print_code(self, file_path, start_line, color=None):
        lines = self.read_code_from_file(file_path, start_line)
        for line_number, line in lines:
            if line.strip() == "":
                break  # 遇到空行，停止读取

            # 显示行号和行内容
            line_number += 1  # 更新行号计数器
            line_number_info = f"{line_number}".rjust(5, " ") + "|"
            self._display.display(msg=line_number_info + line, color=color)

    # 调用函数并传递文件路径和起始行数
    def get_path(self, task):
        pathspec = task.get_path()
        # self._display.display(msg=pathspec)
        if pathspec:
            path, lineno = pathspec.split(":", 1)
            lineno = int(lineno)
        else:
            # Task doesn't have a path, default to "something"
            path = self.playbook["path"]
            lineno = 1
        return path, lineno, pathspec

    def v2_playbook_on_task_start(self, task, is_conditional):

        try:
            # color_to_log_level = {C.COLOR_ERROR: logging.ERROR,
            #                      C.COLOR_WARN: logging.WARNING,
            #                      C.COLOR_OK: logging.INFO,
            #                      C.COLOR_SKIP: logging.WARNING,
            #                      C.COLOR_UNREACHABLE: logging.ERROR,
            #                      C.COLOR_DEBUG: logging.DEBUG,
            #                      C.COLOR_CHANGED: logging.INFO,
            #                      C.COLOR_DEPRECATE: logging.WARNING,
            #                      C.COLOR_VERBOSE: logging.INFO}

            self.nujnus_task = task
            self.record_pathspec()
            self.check_break()
            if self.continue_flag == False:
                self.display_code()

            # self.debug()

        except Exception as e:
            print(e)

    def check_break(self):
        _, _, pathspec = self.get_path(self.nujnus_task)
        if pathspec in self.break_list:
            self.continue_flag = False

    def record_pathspec(self):
        _, _, pathspec = self.get_path(self.nujnus_task)
        task_name = self.nujnus_task.get_name()

        self.nujnus_task_path_list.append((pathspec, task_name))

    def comment_code(self, lines_with_number):
        print("asking ai...")
        msg, type = self.get_comment_prompt()
        for line_number, line in lines_with_number:
            line_number_info = f"{line_number+1}".rjust(5, " ") + "|"
            msg += line_number_info + line
        msg += "\n" + type

        print(colorize_code(self.chat(msg, self.chat_history)))

    def analyze_code(self, lines_with_number):
        print("asking ai...")
        msg = self.get_comment_prompt()
        msg, result_prompt, type = self.get_result_prompt()
        for line_number, line in lines_with_number:
            line_number_info = f"{line_number+1}".rjust(5, " ") + "|"
            msg += line_number_info + line
        msg += (
            result_prompt + str(self.result_history[-1][1]._result) + "\n" + type
            if len(self.result_history) > 0
            else None
        )
        print(colorize_code(self.chat(msg, self.chat_history)))

    def ask_ai(self, for_what):
        try:
            if self.enable_ai:

                path, lineno, pathspec = self.get_path(self.nujnus_task)
                file_path, start_line, color = path, lineno, C.COLOR_DEBUG

                lines = self.read_code_from_file(file_path, start_line)
                if len(lines) == 0:
                    warning = "Start line exceeds the total number of lines in the file or task not exist."
                    self._display.display(msg=warning, color=C.COLOR_WARN)
                if for_what == ASK_AI_TO_COMMENT:
                    self.comment_code(lines_with_number=lines)
                elif for_what == ASK_AI_TO_ANALYZE:
                    self.analyze_code(lines_with_number=lines)
                else:
                    pass

            else:
                print(
                    "Env variables OPENAI_API_KEY or OPENAI_API_URL or OPENAI_MODEL not set"
                )
        except FileNotFoundError:
            print("File not found.")
        except Exception as e:
            print(f"An error occurred: {e}")

    def ask(self, user_input):
        if self.enable_ai:
            path, lineno, pathspec = self.get_path(self.nujnus_task)
            file_path, start_line, color = path, lineno, C.COLOR_DEBUG

            try:
                with open(file_path, "r") as file:
                    content = file.read()
                    pre_prompt, post_prompt = self.get_ask_prompt()
                    msg = f"{pre_prompt}\n{content}\n{post_prompt}{user_input}"
                    print(colorize_code(self.chat(msg, self.chat_history)))

            except FileNotFoundError:
                print("File not found.")
            except Exception as e:
                print(f"An error occurred: {e}")
        else:
            print(
                "Env variables OPENAI_API_KEY or OPENAI_API_URL or OPENAI_MODEL not set"
            )

    # def ask_code_result(self):
    #    if self.enable_ai:
    #        path, lineno, pathspec = self.get_path(self.nujnus_task)
    #        file_path, start_line, color = path, lineno, C.COLOR_DEBUG

    #        try:
    #            with open(file_path, "r") as file:
    #                lines = file.readlines()
    #                total_lines = len(lines)
    #                msg, result_prompt = self.get_result_prompt()
    #                if start_line <= total_lines:
    #                    for i in range(
    #                        start_line - 1, min(start_line + 9, total_lines)
    #                    ):
    #                        line_number_info = f"{i+1}".rjust(5, " ") + "|"
    #                        msg += line_number_info + lines[i]
    #                    msg += (
    #                        result_prompt + str(self.result_history[-1][1]._result)
    #                        if len(self.result_history) > 0
    #                        else None
    #                    )
    #                    print(colorize_code(self.chat(msg, self.chat_history)))
    #                else:
    #                    warning = (
    #                        "Start line exceeds the total number of lines in the file."
    #                    )
    #                    self._display.display(msg=warning, color=C.COLOR_WARN)

    #        except FileNotFoundError:
    #            print("File not found.")
    #        except Exception as e:
    #            print(f"An error occurred: {e}")
    #    else:
    #        print("Env variables OPENAI_API_KEY or OPENAI_API_URL not set")

    def display_code(self):

        path, lineno, pathspec = self.get_path(self.nujnus_task)
        task_name = self.nujnus_task.get_name()

        # Get task file
        # task_file = self._get_or_create_file(path)
        self._display.display(msg="DEBUG INFO:", color=C.COLOR_DEBUG)
        self._display.display(msg=pathspec, color=C.COLOR_DEBUG)
        # self._display.display(
        #    msg=f"Displaying 10 lines starting from line {lineno}:"
        # )
        self._display.display(msg="\n```", color=C.COLOR_DEBUG)
        self.print_code(path, lineno, C.COLOR_DEBUG)
        # self._display.display("File not in cache, getting or creating: %s" % path)
        self._display.display(msg="```\n\n", color=C.COLOR_DEBUG)

    def execute_and_capture_output(self, code, context):
        # 创建一个 StringIO 对象用于捕获输出
        capture_output = StringIO()
        # 使用 redirect_stdout 将输出重定向到 StringIO 对象
        with redirect_stdout(capture_output):
            try:
                # 使用compile将输入编译为表达式并执行
                compiled_input = compile(code, "<string>", "eval")
                result = eval(compiled_input, context)
                if result is not None:  # 如果有返回结果，则打印它
                    print(result)

            except Exception as e:
                # 打印执行时发生的异常
                print(f"Error: {e}")
        # 获取并返回捕获的输出
        return capture_output.getvalue()

    # def v2_runner_on_ok(self, result, **kwargs):

    # ||def v2_runner_on_failed(self, result, ignore_errors=False):
    # ||    #self.debug_record_result(result)
    # ||    pass

    def display_invocation(self, result):
        self._display.display(
            "         taskname: %s" % self.nujnus_task.get_name().strip(),
            color=C.COLOR_CHANGED,
        )
        self._display.display(
            "expanded taskname: %s" % result.task_name, color=C.COLOR_CHANGED
        )
        self._display.display(
            "         module  : %s" % result._task.action, color=C.COLOR_CHANGED
        )
        self._display.display(
            "         args    : %s" % self.nujnus_task.args, color=C.COLOR_CHANGED
        )
        self._display.display(
            "expanded args    : %s"
            % result._result.get(
                "invocation", {"not found": "maybe not implemented"}
            ).get("module_args", {"not found": "maybe not implemented"}),
            color=C.COLOR_CHANGED,
        )

    def v2_runner_on_ok(self, result):
        # print(result._host)
        # Print("ok")
        self.debug_record_result(result)
        # self.display_invocation(result)
        self.debug()
        # 检查是否在ouput_list中, 如果是, 将result输出到output文件中
        if self.check_output_point():
            self.append_result_to_file_with_path_check(self.output_file_path, result)

    def v2_runner_on_skipped(self, result):
        self._display.display("skipped:{}".format(result._host), C.COLOR_SKIP)
        # pass
        # self.debug_record_result(result)
        # self.debug() # 跳过的任务, 就不再debug
        ## self.display_invocation(result)
        # super().v2_runner_on_skipped(result)

    def v2_runner_on_unreachable(self, result):
        self._display.display(
            "unreachable:{}".format(result._host), C.COLOR_UNREACHABLE
        )
        self.debug_record_result(result)
        self.debug()
        # pass
        # self.debug_record_result(result)
        ## self.display_invocation(result)
        # self.debug()

    def v2_runner_on_no_hosts(self, task):
        print("no hosts")
        pass

    def v2_runner_on_async_poll(self, result):
        self._display.display("async poll:{}".format(result._host), C.COLOR_OK)
        # self.debug_record_result(result)
        # pass
        self.debug_record_result(result)
        # self.display_invocation(result)
        self.debug()

    def v2_runner_on_async_ok(self, host, result):
        self._display.display("async ok:{}".format(result._host), C.COLOR_OK)
        self.debug_record_result(result)
        # pass
        # self.display_invocation(result)
        self.debug()

    def v2_runner_on_failed(self, result, ignore_errors=False):
        self._display.display("failed:{}".format(result._host), C.COLOR_ERROR)
        self.continue_flag = False
        self.debug_record_result(result)
        self.debug()

    def v2_runner_on_async_failed(self, result):
        self._display.display("async failed:{}".format(result._host), C.COLOR_ERROR)
        self.continue_flag = False
        # self.debug_record_result(result)
        # pass
        self.debug_record_result(result)
        # self.display_invocation(result)
        self.debug()

    def debug_record_result(self, result, *args, **kwargs):
        # 记录上一个task运行的result
        _, _, pathspec = self.get_path(self.nujnus_task)
        # host = result._host
        # host_vars = host.vars

        self.result_history.append((pathspec, result))
        # ||# self.result_history.append((pathspec, host_vars))
        # ||# 打印主机变量
        # ||host_vars = host.vars
        # ||print(f"Host Variables for {host.name}: {host_vars}")

        # ||# 任务变量（在 result._result 中）
        # ||task_vars = result._result
        # ||print(f"Task Variables for {host.name}: {task_vars}")

        # ||# 组变量 (需要从 host 的 groups 属性中提取)
        # ||group_vars = {}
        # ||for group in host.groups:
        # ||    group_vars[group.name] = group.vars
        # ||print(f"Group Variables for {host.name}: {group_vars}")

    def debug(self):
        if self.continue_flag == False:

            try:
                # 确保在调用input之前flush输出，以避免输出顺序问题
                sys.stdout.flush()

                # 定义样式
                style = Style.from_dict(
                    {
                        "prompt": "fg:ansiyellow",  # 使用 ANSI 颜色名称
                        # 可以添加更多的样式设置
                    }
                )

                # 创建 PromptSession 实例，设置编辑模式为 VI 并传入历史记录对象, 支持上下自动填入历史的功能
                if self.AIANSIBLE_EDITMODE == "vi":
                    session = PromptSession(
                        editing_mode=EditingMode.VI,
                        history=CallbackModule.history,
                        style=style,
                    )
                elif self.AIANSIBLE_EDITMODE == "emacs":
                    session = PromptSession(
                        editing_mode=EditingMode.EMACS,
                        history=CallbackModule.history,
                        style=style,
                    )
                else:
                    session = PromptSession(
                        editing_mode=EditingMode.EMACS,
                        history=CallbackModule.history,
                        style=style,
                    )

                # context = {"__builtins__": __builtins__, "result": result, "self": self}
                context = {
                    "__builtins__": __builtins__,
                    "result_history": self.result_history,
                    "result": (
                        self.result_history[-1][1]
                        if len(self.result_history) > 0
                        else None
                    ),
                    "self": self,
                }
                while True:
                    if self.move_on_at_task == self.get_path(self.nujnus_task):
                        print("keep moving =>")
                        break
                    else:  # 重置, 说明暂时已经结束了self.move_on_at_task所指向的任务, 考虑到可能会循环到这个任务, 所以重置为None:
                        self.move_on_at_task == None

                    action = ""
                    args = []
                    # 使用 prompt 函数读取用户输入，提供历史记录功能
                    # user_input = prompt("Aiansible => ", history=history)
                    user_input = session.prompt(f"Aiansible({self.aiansible_lang}) => ")
                    # 执行输入的 Python 代码
                    # exec(user_input)
                    _user_input = user_input.split()
                    if len(_user_input) > 0:
                        action = _user_input[0]
                    if len(_user_input) > 1:
                        args = _user_input[1:]

                    if user_input.lower() == "exit":

                        user_input = input("是否结束运行? (y/n): ")
                        if user_input.lower() == "y":
                            # 交互式操作
                            print("任务被用户中断!")
                            sys.exit(0)  # 或者使用更合适的方式来优雅地停止Ansible执行

                    elif action.lower() == ":cn":
                        self.aiansible_lang = "CN"
                    elif action.lower() == ":en":
                        self.aiansible_lang = "EN"
                    elif action.lower() == "next" or action.lower() == "n":
                        break  # 用户输入 exit 时退出循环
                    elif action.lower() == "m":  # moveon
                        self.move_on_at_task = self.get_path(
                            self.nujnus_task
                        )  # 获取最后执行的任务的路径
                        break  # 用户输入 exit 时退出循环
                    elif action.lower() == "break" or action.lower() == "b":
                        _, _, pathspec = self.get_path(
                            self.nujnus_task
                        )  # 获取最后执行的任务的路径
                        self.save_to_break_list(pathspec)
                    elif action.lower() == "output" or action.lower() == "o":
                        _, _, pathspec = self.get_path(
                            self.nujnus_task
                        )  # 获取最后执行的任务的路径
                        self.save_to_output_list(pathspec)

                    elif action.lower() == "i":
                        self.ask_ai(for_what=ASK_AI_TO_COMMENT)  # 查看注释
                    elif action.lower() == "ir":
                        self.ask_ai(for_what=ASK_AI_TO_ANALYZE)  # 查看注释
                    elif action.lower() == "ask":
                        self.ask(user_input)  # 请求分析结果
                    elif action.lower() == "p":  # print break_point list
                        _, _, pathspec = self.get_path(self.nujnus_task)
                        for index, p in enumerate(self.break_list):
                            if (
                                pathspec == p
                            ):  # 比较最后执行的任务的路径, 和 breakpoint_list中任务的路径
                                self._display.display(
                                    f"{index}:{p}",
                                    color=C.COLOR_OK,
                                )
                            else:
                                self._display.display(
                                    f"{index}:{p}",
                                    color=C.COLOR_DEBUG,
                                )
                    elif action.lower() == "op":  # print break_point list
                        _, _, pathspec = self.get_path(self.nujnus_task)
                        for index, p in enumerate(self.output_list):
                            if (
                                pathspec == p
                            ):  # 比较最后执行的任务的路径, 和 breakpoint_list中任务的路径
                                self._display.display(
                                    f"{index}:{p}",
                                    color=C.COLOR_OK,
                                )
                            else:
                                self._display.display(
                                    f"{index}:{p}",
                                    color=C.COLOR_DEBUG,
                                )
                    elif action.lower() == "do":  # delete output point
                        # 删除断点
                        if len(args) == 1:
                            if is_natural_number(args[0]):
                                self.delete_one_output_point(index=int(args[0]))

                        elif len(args) == 0:
                            _, _, pathspec = self.get_path(self.nujnus_task)
                            self.delete_one_output_point(
                                index=self.break_list.index(pathspec)
                            )

                    elif action.lower() == "delete" or action.lower() == "d":
                        # 删除断点
                        if len(args) == 1:

                            if is_natural_number(args[0]):
                                self.delete_one_break(index=int(args[0]))

                        elif len(args) == 0:
                            _, _, pathspec = self.get_path(self.nujnus_task)
                            self.delete_one_break(index=self.break_list.index(pathspec))

                    elif action.lower() == "continue" or action.lower() == "c":
                        # 执行到下一个断点
                        self.continue_flag = True
                        break
                    elif action.lower() == "?" or action.lower() == "help":
                        if self.aiansible_lang == "CN":
                            help = HELP
                        elif self.aiansible_lang == "EN":
                            help = ENGLISH_HELP
                        else:
                            help = HELP
                        print(help)
                    # elif action.lower() == "rc":
                    #    try:
                    #        if len(self.result_history) > 0:
                    #            result = self.result_history[-1][1]
                    #            self.display_invocation(result)

                    #        if len(self.result_history) > 0:
                    #            result = self.result_history[-1][1]
                    #            host = result._host
                    #            result_string = json.dumps(
                    #                result._result, indent=4, sort_keys=True
                    #            )
                    #            self._display.display(
                    #                # self._dump_results(result),
                    #                f"result => {result_string}",
                    #                color=C.COLOR_DEBUG,
                    #            )

                    #    except Exception as e:
                    #        print(e)
                    elif action.lower() == "bt":
                        try:
                            for index, pathspec_task in enumerate(
                                self.nujnus_task_path_list
                            ):
                                self._display.display(
                                    msg=f"{index}:"
                                    + pathspec_task[0]
                                    + "=>"
                                    + pathspec_task[1],
                                    color=C.COLOR_DEBUG,
                                )

                        except Exception as e:
                            print(e)
                    elif action.lower() == "code":
                        self.display_code()
                    elif action.lower() == "vscode" or action.lower() == "v":
                        if len(args) == 1:

                            if is_natural_number(args[0]):
                                _, _, pathspec = self.get_path(self.nujnus_task)
                                if int(args[0]) <= (
                                    len(self.nujnus_task_path_list) - 1
                                ):
                                    pathspec = self.nujnus_task_path_list[int(args[0])][
                                        0
                                    ]
                                    subprocess.run(["code", "-g", pathspec])

                        elif len(args) == 0:
                            # vscode 用命令行 打开特定文件, 并跳转到特定行
                            _, _, pathspec = self.get_path(self.nujnus_task)
                            subprocess.run(["code", "-g", pathspec])

                    elif not user_input.strip():
                        pass
                        # self._display.display(
                        #    msg="未检测到输入，请重新输入。", color=C.COLOR_WARN
                        # )
                    elif action.lower() == "name":
                        # 删除断点
                        if len(args) == 1:
                            print("name命令不支持参数")

                        elif len(args) == 0:
                            try:
                                output = self.execute_and_capture_output(
                                    "result.task_name", context
                                )
                                print(output)
                            except Exception as e:
                                print(e)

                    elif action.lower() == "arg" or action.lower() == "a":
                        # 删除断点
                        if len(args) == 1:

                            try:
                                output = self.execute_and_capture_output(
                                    f'result._task_fields["args"]["{args[0]}"]', context
                                )
                                print(output)
                            except Exception as e:
                                print(e)

                        elif len(args) == 0:
                            try:
                                output = self.execute_and_capture_output(
                                    'print(\'\\n\'.join(f"{k}: {v}" for k, v in result._task_fields["args"].items()))',
                                    context,
                                )
                                print(output)
                            except Exception as e:
                                print(e)

                    else:
                        try:
                            output = self.execute_and_capture_output(
                                user_input, context
                            )
                            print(output)
                        except Exception as e:
                            print(e)

            except Exception as e:
                print(e)
