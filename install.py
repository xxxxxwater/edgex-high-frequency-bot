#!/usr/bin/env python3
"""
安装脚本
"""

import subprocess
import sys
import os
from loguru import logger

def run_command(cmd):
    """运行命令"""
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        logger.info(f"命令执行成功: {cmd}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"命令执行失败: {cmd}")
        logger.error(f"错误输出: {e.stderr}")
        return False

def install_dependencies():
    """安装依赖"""
    logger.info("安装Python依赖...")
    
    # 升级pip
    if not run_command(f"{sys.executable} -m pip install --upgrade pip"):
        logger.warning("pip升级失败，继续安装依赖...")
    
    # 安装依赖
    if not run_command(f"{sys.executable} -m pip install -r requirements.txt"):
        logger.error("依赖安装失败")
        return False
    
    logger.info("依赖安装完成")
    return True

def setup_config():
    """设置配置"""
    logger.info("设置配置文件...")
    
    # 检查配置文件是否存在
    if not os.path.exists("config_local.py"):
        if os.path.exists("config_local.py.template"):
            logger.info("复制配置文件模板...")
            if not run_command("cp config_local.py.template config_local.py"):
                logger.error("配置文件复制失败")
                return False
        else:
            logger.error("找不到配置文件模板")
            return False
    
    # 检查环境变量文件
    if not os.path.exists(".env"):
        if os.path.exists("env.template"):
            logger.info("复制环境变量模板...")
            if not run_command("cp env.template .env"):
                logger.error("环境变量文件复制失败")
                return False
    
    logger.info("配置文件设置完成")
    logger.info("请编辑 config_local.py 文件，填入您的API密钥")
    return True

def create_directories():
    """创建必要目录"""
    logger.info("创建必要目录...")
    
    directories = ["logs", "data"]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"创建目录: {directory}")
    
    return True

def main():
    """主函数"""
    logger.info("EdgeX高频交易机器人安装程序")
    
    # 安装依赖
    if not install_dependencies():
        logger.error("安装失败")
        sys.exit(1)
    
    # 设置配置
    if not setup_config():
        logger.error("配置设置失败")
        sys.exit(1)
    
    # 创建目录
    if not create_directories():
        logger.error("目录创建失败")
        sys.exit(1)
    
    logger.info("安装完成！")
    logger.info("下一步:")
    logger.info("1. 编辑 config_local.py 文件，填入您的API密钥")
    logger.info("2. 运行 python start.py 启动程序")

if __name__ == "__main__":
    main()
