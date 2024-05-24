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
import re
import json

import yaml
from openai import OpenAI
import re


GREEN = "\033[92m"
RED = "\033[91m"
BLUE = "\033[34m"
YELLOW = "\033[93m"
RESET = "\033[0m"


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


class CallbackModule(CallbackBase):

    history = InMemoryHistory()

    def __init__(self, display=None, options=None):
        super().__init__(display=display, options=options)
        self.nujnus_task_path_list = []
        # 读取断点清单文件
        self.break_list_file_path = os.environ.get("BREAK_LIST_FILE_PATH")
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

        self.ai_client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_API_URL"),
        )
        self.chat_context = {
            "role": "system",
            "content": "你是 commentator，你更擅长中文和英文的对话。你会为用户提供安全，有帮助，准确的回答。",  # 你会根据用户给出的代码, 在用户给出的代码之后写出用中文进行的注释, 你会将用户给出的代码 和你的注释合并在一起.
        }

        self.chat_history = []
        self.chat_history.append(self.chat_context)

    def chat(self, query, history):
        self.chat_history.append({"role": "user", "content": query})
        completion = self.ai_client.chat.completions.create(
            model="moonshot-v1-8k",
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

    def display_lines_from_file(self, file_path, start_line, color=None):
        try:
            with open(file_path, "r") as file:
                lines = file.readlines()
                total_lines = len(lines)

                if start_line <= total_lines:
                    for i in range(start_line - 1, min(start_line + 9, total_lines)):
                        line_number_info = f"{i+1}".rjust(5, " ") + "|"
                        self._display.display(
                            msg=line_number_info + lines[i], color=color
                        )
                else:
                    warning = (
                        "Start line exceeds the total number of lines in the file."
                    )
                    self._display.display(msg=warning, color=C.COLOR_WARN)

        except FileNotFoundError:
            print("File not found.")
        except Exception as e:
            print(f"An error occurred: {e}")

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

    def ask_code_comment(self):

        path, lineno, pathspec = self.get_path(self.nujnus_task)
        file_path, start_line, color = path, lineno, C.COLOR_DEBUG

        try:
            with open(file_path, "r") as file:
                lines = file.readlines()
                total_lines = len(lines)
                msg = "用中文, 在每行代码后的同一行内, 注释一下如下代码(注意:除此之外,不需要额外说明 ):"
                if start_line <= total_lines:
                    for i in range(start_line - 1, min(start_line + 9, total_lines)):
                        line_number_info = f"{i+1}".rjust(5, " ") + "|"
                        msg += line_number_info + lines[i]
                    print(colorize_code(self.chat(msg, self.chat_history)))
                else:
                    warning = (
                        "Start line exceeds the total number of lines in the file."
                    )
                    self._display.display(msg=warning, color=C.COLOR_WARN)

        except FileNotFoundError:
            print("File not found.")
        except Exception as e:
            print(f"An error occurred: {e}")

    def ask(self, user_input):
        path, lineno, pathspec = self.get_path(self.nujnus_task)
        file_path, start_line, color = path, lineno, C.COLOR_DEBUG

        try:
            with open(file_path, "r") as file:
                content = file.read()
                msg = f"请根据当前ansible任务:\n{content}\n回答如下问题:{user_input}"
                print(colorize_code(self.chat(msg, self.chat_history)))

        except FileNotFoundError:
            print("File not found.")
        except Exception as e:
            print(f"An error occurred: {e}")

    def ask_code_result(self):
        path, lineno, pathspec = self.get_path(self.nujnus_task)
        file_path, start_line, color = path, lineno, C.COLOR_DEBUG

        try:
            with open(file_path, "r") as file:
                lines = file.readlines()
                total_lines = len(lines)
                msg = "用中文, 在每行代码后的同一行内, 注释一下如下代码, 再分析一下运行结果的原因, 再告诉我该如何改进(注意:除此之外,不需要额外说明 ):"
                if start_line <= total_lines:
                    for i in range(start_line - 1, min(start_line + 9, total_lines)):
                        line_number_info = f"{i+1}".rjust(5, " ") + "|"
                        msg += line_number_info + lines[i]
                    msg += (
                        "\n运行结果为:" + str(self.result_history[-1][1]._result)
                        if len(self.result_history) > 0
                        else None
                    )
                    print(colorize_code(self.chat(msg, self.chat_history)))
                else:
                    warning = (
                        "Start line exceeds the total number of lines in the file."
                    )
                    self._display.display(msg=warning, color=C.COLOR_WARN)

        except FileNotFoundError:
            print("File not found.")
        except Exception as e:
            print(f"An error occurred: {e}")

    def display_code(self):

        path, lineno, pathspec = self.get_path(self.nujnus_task)
        task_name = self.nujnus_task.get_name()

        self.nujnus_task_path_list.append((pathspec, task_name))

        # Get task file
        # task_file = self._get_or_create_file(path)
        self._display.display(msg="DEBUG INFO:", color=C.COLOR_DEBUG)
        self._display.display(msg=pathspec, color=C.COLOR_DEBUG)
        # self._display.display(
        #    msg=f"Displaying 10 lines starting from line {lineno}:"
        # )
        self._display.display(msg="\n```", color=C.COLOR_DEBUG)
        self.display_lines_from_file(path, lineno, C.COLOR_DEBUG)
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

                # 创建 PromptSession 实例，设置编辑模式为 VI 并传入历史记录对象, 支持上下自动填入历史的功能
                session = PromptSession(
                    editing_mode=EditingMode.VI, history=CallbackModule.history
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
                    user_input = session.prompt("Aiansible => ")
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
                        # self.display_code()
                        self.ask_code_comment()  # 查看注释
                    elif action.lower() == "ir":
                        self.ask_code_result()  # 请求分析结果
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
                        help = """
n    next      运行下一个任务
m              不再在紧接着的同一个任务处停留
c    continue  继续运行直到下一个断点
b              创建断点
p              查看已经创建的断点
d    delete    删除断点
bt             查看已经运行过哪些任务了
code           查看正在运行的任务
v              用vscode打开对应文件
a    arg       查看所有参数, 或单个参数 (在任务没有被skipped的前提下)
?    help      查看使用说明
exit           退出
                        """
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