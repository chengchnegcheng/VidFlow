"""
ISAAC64 伪随机数生成器

微信视频号使用 ISAAC64 (Indirection, Shift, Accumulate, Add, and Count)
流加密方案对视频前 128KB 进行加密。

参考实现：
- github.com/nobiyou/wx_channel (Go)
- github.com/ltaoo/wx_channels_download (Go)
- github.com/Hanson/WechatSphDecrypt (Go)
"""

import struct
from typing import Optional

# 加密区域大小：只有文件前 128KB 被加密
ENCRYPTED_PREFIX_LENGTH = 131072  # 128 * 1024

# 64 位无符号整数掩码
MASK64 = 0xFFFFFFFFFFFFFFFF

# 黄金比例常数
GOLDEN_RATIO = 0x9e3779b97f4a7c13


def _u64(val: int) -> int:
    """截断为 64 位无符号整数"""
    return val & MASK64


class Isaac64:
    """ISAAC64 伪随机数生成器

    用于微信视频号视频解密。使用 decodeKey (uint64) 作为种子，
    生成伪随机字节流，与视频前 128KB 做 XOR 解密。
    """

    def __init__(self, seed: int):
        """初始化 ISAAC64

        Args:
            seed: uint64 种子（微信 API 返回的 decodeKey）
        """
        self._randrsl = [0] * 256  # 随机数输出缓冲区
        self._randcnt = 0          # 剩余可用随机数计数
        self._mm = [0] * 256       # 内部状态数组
        self._aa = 0               # 累加器 A
        self._bb = 0               # 累加器 B
        self._cc = 0               # 计数器 C

        self._randrsl[0] = _u64(seed)
        self._randinit()

    def _mix(self, a: int, b: int, c: int, d: int,
             e: int, f: int, g: int, h: int):
        """8 变量混合函数"""
        a = _u64(a - e);  f = _u64(f ^ _u64(h >> 9));   h = _u64(h + a)
        b = _u64(b - f);  g = _u64(g ^ _u64(a << 9));   a = _u64(a + b)
        c = _u64(c - g);  h = _u64(h ^ _u64(b >> 23));  b = _u64(b + c)
        d = _u64(d - h);  a = _u64(a ^ _u64(c << 15));  c = _u64(c + d)
        e = _u64(e - a);  b = _u64(b ^ _u64(d >> 14));  d = _u64(d + e)
        f = _u64(f - b);  c = _u64(c ^ _u64(e << 20));  e = _u64(e + f)
        g = _u64(g - c);  d = _u64(d ^ _u64(f >> 17));  f = _u64(f + g)
        h = _u64(h - d);  e = _u64(e ^ _u64(g << 14));  g = _u64(g + h)
        return a, b, c, d, e, f, g, h

    def _randinit(self):
        """初始化内部状态"""
        a = b = c = d = e = f = g = h = GOLDEN_RATIO

        # 预混合 4 轮
        for _ in range(4):
            a, b, c, d, e, f, g, h = self._mix(a, b, c, d, e, f, g, h)

        # 第一轮：用 seed 数组混合初始化 mm
        for j in range(0, 256, 8):
            a = _u64(a + self._randrsl[j])
            b = _u64(b + self._randrsl[j + 1])
            c = _u64(c + self._randrsl[j + 2])
            d = _u64(d + self._randrsl[j + 3])
            e = _u64(e + self._randrsl[j + 4])
            f = _u64(f + self._randrsl[j + 5])
            g = _u64(g + self._randrsl[j + 6])
            h = _u64(h + self._randrsl[j + 7])
            a, b, c, d, e, f, g, h = self._mix(a, b, c, d, e, f, g, h)
            self._mm[j] = a
            self._mm[j + 1] = b
            self._mm[j + 2] = c
            self._mm[j + 3] = d
            self._mm[j + 4] = e
            self._mm[j + 5] = f
            self._mm[j + 6] = g
            self._mm[j + 7] = h

        # 第二轮：用 mm 自身再次混合
        for j in range(0, 256, 8):
            a = _u64(a + self._mm[j])
            b = _u64(b + self._mm[j + 1])
            c = _u64(c + self._mm[j + 2])
            d = _u64(d + self._mm[j + 3])
            e = _u64(e + self._mm[j + 4])
            f = _u64(f + self._mm[j + 5])
            g = _u64(g + self._mm[j + 6])
            h = _u64(h + self._mm[j + 7])
            a, b, c, d, e, f, g, h = self._mix(a, b, c, d, e, f, g, h)
            self._mm[j] = a
            self._mm[j + 1] = b
            self._mm[j + 2] = c
            self._mm[j + 3] = d
            self._mm[j + 4] = e
            self._mm[j + 5] = f
            self._mm[j + 6] = g
            self._mm[j + 7] = h

        # 生成第一批随机数
        self._isaac64()
        self._randcnt = 256

    def _isaac64(self):
        """生成 256 个 uint64 随机数"""
        self._cc = _u64(self._cc + 1)
        self._bb = _u64(self._bb + self._cc)

        for j in range(256):
            x = self._mm[j]

            # 4 种位移模式轮换
            remainder = j % 4
            if remainder == 0:
                self._aa = _u64(~self._aa ^ _u64(self._aa << 21))
            elif remainder == 1:
                self._aa = _u64(self._aa ^ _u64(self._aa >> 5))
            elif remainder == 2:
                self._aa = _u64(self._aa ^ _u64(self._aa << 12))
            else:
                self._aa = _u64(self._aa ^ _u64(self._aa >> 33))

            self._aa = _u64(self._aa + self._mm[(j + 128) % 256])
            y = _u64(self._mm[_u64(x >> 3) % 256] + self._aa + self._bb)
            self._mm[j] = y
            self._bb = _u64(self._mm[_u64(y >> 11) % 256] + x)
            self._randrsl[j] = self._bb

    def generate(self, length: int) -> bytes:
        """生成指定长度的伪随机字节序列

        Args:
            length: 需要生成的字节数

        Returns:
            伪随机字节序列
        """
        result = bytearray(length)
        pos = 0

        while pos < length:
            if self._randcnt == 0:
                self._isaac64()
                self._randcnt = 256

            self._randcnt -= 1
            val = self._randrsl[self._randcnt]

            # 将 uint64 转为 8 字节（大端序）
            val_bytes = struct.pack('>Q', _u64(val))
            for k in range(8):
                if pos >= length:
                    break
                result[pos] = val_bytes[k]
                pos += 1

        return bytes(result)


def generate_decryptor_array(seed: int, length: int = ENCRYPTED_PREFIX_LENGTH) -> bytes:
    """生成解密数组

    Args:
        seed: uint64 种子（decodeKey）
        length: 解密数组长度，默认 128KB

    Returns:
        解密用的伪随机字节数组
    """
    isaac = Isaac64(seed)
    return isaac.generate(length)


def decrypt_video_data(data: bytes, seed: int) -> bytes:
    """解密视频数据

    对数据的前 128KB 与 ISAAC64 生成的伪随机流做 XOR。
    超过 128KB 的部分不加密，直接保留。

    Args:
        data: 加密的视频数据
        seed: uint64 种子（decodeKey）

    Returns:
        解密后的视频数据
    """
    decryptor = generate_decryptor_array(seed, min(len(data), ENCRYPTED_PREFIX_LENGTH))

    result = bytearray(data)
    for i in range(len(decryptor)):
        result[i] ^= decryptor[i]

    return bytes(result)


def decrypt_video_file(file_path: str, seed: int) -> bool:
    """原地解密视频文件

    读取文件前 128KB，与 ISAAC64 输出 XOR 后写回。

    Args:
        file_path: 文件路径
        seed: uint64 种子（decodeKey）

    Returns:
        解密成功返回 True
    """
    import os

    file_size = os.path.getsize(file_path)
    if file_size == 0:
        return False

    prefix_len = min(file_size, ENCRYPTED_PREFIX_LENGTH)
    decryptor = generate_decryptor_array(seed, prefix_len)

    with open(file_path, 'r+b') as f:
        chunk = f.read(prefix_len)
        decrypted = bytearray(chunk)
        for i in range(len(decryptor)):
            decrypted[i] ^= decryptor[i]
        f.seek(0)
        f.write(decrypted)

    return True
