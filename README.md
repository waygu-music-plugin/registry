# Wagyu Music 官方插件目录

在 [Wagyu Music](https://github.com/vicnoah/mygo-cloudmusic) 的「插件管理」选择对应插件包并点击「安装或更新」。官方目录地址已随应用提供，也可以在来源设置中填写。

```text
https://raw.githubusercontent.com/waygu-music-plugin/registry/main/catalog.json
```

| 插件包 | 提供的平台 |
| --- | --- |
| [Songloft](https://github.com/waygu-music-plugin/songloft/releases) | Songloft |
| [Subsonic](https://github.com/waygu-music-plugin/subsonic/releases) | Navidrome、Jellyfin、Gonic、通用 Subsonic |
| [网易云音乐](https://github.com/waygu-music-plugin/netease/releases) | 网易云音乐 |
| [QQ 音乐](https://github.com/waygu-music-plugin/qqmusic/releases) | QQ 音乐 |

四个插件包均提供 Windows、macOS 和 Linux 的 amd64、arm64 产物。应用使用协议 v1，校验签名清单和归档散列，并在安装前启动程序验证入口。飞牛音乐随主程序发布。

## 构建插件发行

`build_release.py` 在 Linux 上交叉编译六个目标，生成 ZIP、SHA-256、签名清单和包目录。需要 Go、Python 3.11+、OpenSSL 和已有的 Ed25519 发布密钥。

```sh
python3 build_release.py --source ../songloft --tag v0.1.0 --key /path/to/publisher.pem --out ./build/songloft
```

先在相应插件仓库发布生成的文件，再将该版本的 `catalog.json` 中对应的包条目写入本目录。已安装的插件会固定来源和签名公钥。
