# Copyright (c) Opendatalab. All rights reserved.
import hashlib
import json


def bytes_md5(file_bytes):
    hasher = hashlib.md5()
    hasher.update(file_bytes)
    return hasher.hexdigest().upper()


def str_md5(input_string):
    hasher = hashlib.md5()
    # 在Python3中，需要将字符串转化为字节对象才能被哈希函数处理
    input_bytes = input_string.encode('utf-8')
    hasher.update(input_bytes)
    return hasher.hexdigest()


def str_sha256(input_string):
    hasher = hashlib.sha256()
    # 在Python3中，需要将字符串转化为字节对象才能被哈希函数处理
    input_bytes = input_string.encode('utf-8')
    hasher.update(input_bytes)
    return hasher.hexdigest()


def dict_md5(d):
    json_str = json.dumps(d, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(json_str.encode('utf-8')).hexdigest()


def file_md5(file_path, chunk_size=4096):
    """
    计算文件的MD5哈希值
    :param file_path: 文件路径
    :param chunk_size: 分块大小（默认4096字节）
    :return: 文件的MD5值（十六进制字符串）
    """
    md5_hash = hashlib.md5()  # 创建MD5哈希对象
    
    try:
        with open(file_path, "rb") as f:  # 以二进制模式打开文件
            # 分块读取文件并更新哈希
            while chunk := f.read(chunk_size):
                md5_hash.update(chunk)
        
        # 返回十六进制格式的哈希值
        return md5_hash.hexdigest()
    except FileNotFoundError:
        raise FileNotFoundError(f"文件不存在: {file_path}")
    except Exception as e:
        raise Exception(f"计算MD5失败: {str(e)}")