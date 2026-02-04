#!/bin/bash

# LLM-TT 环境安装脚本
# 使用 conda 创建并配置环境

set -e  # 遇到错误立即退出

# # 创建 conda 环境
# conda create -n leo-agent python=3.13 -y
# conda activate leo-agent

# 安装依赖
echo "=== 安装项目依赖 ==="
pip install "baidusearch>=1.0.3"
pip install "ipykernel>=6.29.5"
pip install "loguru>=0.7.3"
pip install "mcp[cli]>=1.7.1"
pip install "mkdocs-include-markdown-plugin>=7.1.5"
pip install "mkdocs-material>=9.6.14"
pip install "mkdocstrings[python]>=0.29.1"
pip install "openai>=1.76.2"