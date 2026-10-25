# 开发与测试

## 常用命令

```sh
make test       # 主机合成测试：核心解析、单槽位保护及运行时映像匹配
make build      # EFI 程序、独立 ISO、校验值与许可文件
make vm-test    # 构建并运行五组隔离 OVMF 测试
```

输出在 `build/`，不进入 Git。虚拟机只连接生成的稀疏测试磁盘；文件中的假
`boot.wim`/`BOOTX64.EFI` 用于检查发现规则，并不是可安装的 Windows 镜像。
`DiscoveryTest.efi` 是只读测试构建，不执行 SMI 或链式启动，不应作为用户入口。

可以通过 `OVMF_DIR` 指定固件目录，默认 `/usr/share/OVMF`，要求包含
`OVMF_CODE_4M.fd` 和 `OVMF_VARS_4M.fd`。

## 产物用途

| 路径（相对 build/） | 用途 |
| --- | --- |
| `dist/AcpiFirst.efi`、`dist/AcpiFirst-Direct-v3-UEFI.iso` | 安装介质的前置 ACPI 启用程序及其启动镜像 |
| `test-only/DiscoveryTest.efi` | 同一源码的只读发现测试构建，不启用 ACPI、不启动 Windows |
| `research/stage3/` | EFI 阶段探针内核与诊断 ISO |
| `research/runtime-inventory/RuntimeInventory.efi` 及同目录 ISO | 采集 EFI 运行时清单，向带标记的日志卷写报告 |
| `research/ec-watch/` | 只读观察 SVAM 前后的 EC 方法地址 |
| `research/ec-slot38/` | 包含显式启用的单槽位临时 RAM 写入，用于因果对照 |

主构建还在 `build/` 根目录保留 `.o`、`.so`、EFI 中间产物；`iso/` 是组装目录，
`vm-tests/` 是临时虚拟磁盘和日志。用户入口以 `dist/` 为准。
研究构建命令和依赖见 [Linux 诊断材料](../research/linux/README.md)。

`BUILD_DIR` 用于主 EFI 构建；Linux 诊断构建及研究 VM 测试使用仓库下的
`build/research/`，内核源码和编译缓存由 `K53_KERNEL_CACHE` 指定。

## 发布产物

建议将构建生成的 `build/dist/` 作为 Release 附件，与源码历史分开。保留其中的
LICENSE、第三方许可和构建清单；ISO 包含的 GRUB 不属于本项目 MIT 许可范围。
构建清单记录实际工具与包版本，不代表生成字节级可重现的 ISO。

当前构建路径与内容测试通过，不等于可在其他型号上运行。平台/FADT 拒绝检查
是当前支持范围的一部分，新增型号前需要新的硬件证据。
