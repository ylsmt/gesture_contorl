#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Created on: 2026-01-07 09:49:13
'''
Description:
Author: Jackie
Version: 1.0
'''

# create_structure.py
import os
import sys

def parse_structure(text, base_path="."):
    """
    根据文本结构创建目录和文件

    Args:
        text: 包含目录结构的文本
        base_path: 基础路径，默认为当前目录
    """
    lines = text.strip().split('\n')

    # 确保基础路径存在
    os.makedirs(base_path, exist_ok=True)

    # 用于跟踪当前缩进级别和路径
    indent_stack = []
    path_stack = [base_path]

    for line in lines:
        # 跳过空行
        if not line.strip():
            continue

        # 计算缩进级别（每2个空格为一级）
        indent_level = 0
        for char in line:
            if char == ' ':
                indent_level += 1
            else:
                break

        # 每2个空格代表一级缩进
        indent_level = indent_level // 2

        # 获取实际内容（去除前导空格）
        content = line.strip()

        # 调整路径栈到正确的缩进级别
        while len(indent_stack) > indent_level:
            indent_stack.pop()
            path_stack.pop()

        # 获取当前路径
        current_path = path_stack[-1]

        # 判断是目录还是文件
        if content.endswith('/'):
            # 这是目录
            dir_name = content.rstrip('/')
            full_dir_path = os.path.join(current_path, dir_name)

            print(f"创建目录: {full_dir_path}")
            os.makedirs(full_dir_path, exist_ok=True)

            # 压入栈
            indent_stack.append(indent_level)
            path_stack.append(full_dir_path)
        else:
            # 这是文件
            full_file_path = os.path.join(current_path, content)

            # 创建文件所在目录（如果不存在）
            file_dir = os.path.dirname(full_file_path)
            if file_dir and not os.path.exists(file_dir):
                print(f"创建目录: {file_dir}")
                os.makedirs(file_dir, exist_ok=True)

            # 创建空文件
            if not os.path.exists(full_file_path):
                print(f"创建文件: {full_file_path}")
                with open(full_file_path, 'w', encoding='utf-8') as f:
                    pass
                    # 可以为特定文件添加初始内容
                    # if full_file_path.endswith('.py'):
                    #     f.write('# -*- coding: utf-8 -*-\n')
                    # elif full_file_path.endswith('.json'):
                    #     f.write('{}\n')
                    # elif full_file_path.endswith('.md'):
                    #     f.write('# 项目说明\n\n')
            else:
                print(f"文件已存在: {full_file_path}")

def create_from_template():
    """使用预定义的模板创建项目结构"""
    structure_text = """
app.py
requirements.txt
config/
  default_config.json
  schema_notes.md
config_io.py
ui/
  main_window.py
  osd.py
  binding_editor.py
vision/
  camera.py
  bare_mediapipe.py
  gesture_primitives.py
  gesture_engine.py
  scroll_state.py
control/
  state.py
  dispatcher.py
  actions.py
  mouse_controller.py
  mouse_worker.py
  app_context.py"""

    return structure_text

def main():
    """主函数"""
    print("开始创建项目结构...")
    print("=" * 50)

    # 获取用户输入的基础路径（默认为当前目录）
    base_path = input("请输入基础路径（默认为当前目录）: ").strip()
    if not base_path:
        base_path = "."

    # 获取用户选择的创建方式
    print("\n选择创建方式:")
    print("1. 使用预定义模板")
    print("2. 从文件读取结构")
    print("3. 手动输入结构")

    choice = input("\n请输入选择 (1/2/3): ").strip()

    if choice == "1":
        # 使用预定义模板
        structure_text = create_from_template()
        print(f"\n使用预定义模板，将在 {os.path.abspath(base_path)} 创建项目结构")
    elif choice == "2":
        # 从文件读取
        file_path = input("请输入结构文件路径: ").strip()
        if not os.path.exists(file_path):
            print(f"错误: 文件 {file_path} 不存在！")
            return
        with open(file_path, 'r', encoding='utf-8') as f:
            structure_text = f.read()
        print(f"\n从文件 {file_path} 读取结构")
    elif choice == "3":
        # 手动输入
        print("\n请输入目录结构（输入空行结束）:")
        print("格式说明: 每行表示一个文件或目录，目录以'/'结尾")
        print("使用2个空格表示一级缩进，例如:")
        print("app.py")
        print("  ui/")
        print("    main_window.py")

        lines = []
        while True:
            line = input()
            if line == "":
                break
            lines.append(line)

        structure_text = '\n'.join(lines)
    else:
        print("无效选择，使用预定义模板")
        structure_text = create_from_template()

    # 解析并创建结构
    print("\n开始创建...")
    print("-" * 50)
    parse_structure(structure_text, base_path)
    print("-" * 50)
    print(f"项目结构创建完成！位置: {os.path.abspath(base_path)}")

    # 显示创建的结构树
    print("\n创建的结构:")
    print_structure_tree(base_path)

def print_structure_tree(root_path, indent=""):
    """打印目录树结构"""
    try:
        items = sorted(os.listdir(root_path))
        for i, item in enumerate(items):
            path = os.path.join(root_path, item)
            is_last = (i == len(items) - 1)

            if os.path.isdir(path):
                print(f"{indent}{'└── ' if is_last else '├── '}{item}/")
                new_indent = indent + ("    " if is_last else "│   ")
                print_structure_tree(path, new_indent)
            else:
                print(f"{indent}{'└── ' if is_last else '├── '}{item}")
    except Exception as e:
        pass

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n操作被用户中断")
    except Exception as e:
        print(f"\n错误: {e}")
        sys.exit(1)