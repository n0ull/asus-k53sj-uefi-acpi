# K53SJ UEFI 启动问题：证据与结论

## 已验证的环境

- ASUS K53SJ，BIOS 315，固件日期 2011-09-26。
- 实机报告为 64 位 UEFI。
- Linux 诊断版本：7.2.7，初始配置来自 Arch `7.2.7.arch1-1`。
- 临时诊断内核用 GCC 13 和上游源码构建，非 Arch 原版二进制的精确重构。
- Windows 测试介质为 x64/x86 双架构 FAT32 安装盘，根目录的原版 64 位引导器带有效微软签名。

## 对照实验

| 测试 | 实机结果 |
| --- | --- |
| Legacy 默认参数启动 Arch | 可进入 Live |
| UEFI 默认参数启动 Arch | 黑屏/冻结 |
| UEFI + `nomodeset` | 未解决 |
| UEFI + `acpi=noirq` | 未解决 |
| UEFI + `acpi=rsdt` | 未解决 |
| UEFI + `acpi=off` | 可进入 Live |
| UEFI + `efi=noruntime`，保留 ACPI | 可进入 Live |
| 诊断内核，默认 ACPI/EFI 顺序 | 停在 ACPI 启用请求边界 |
| 诊断内核，EFI 运行时初始化前调用 `acpi_enable()` | 可进入 shell，EFI 变量服务注册成功 |
| AcpiFirst v3 + 原版 Windows 64 位安装程序 | 可重复进入安装界面 |
| 同一 64 位 UEFI 引导链中选择 32 位 Windows | `winload.efi` / `0xc0000359`，不作为 ACPI 回归证据 |

Windows UEFI 跨架构限制见 [微软部署说明](https://learn.microsoft.com/en-us/windows/deployment/windows-deployment-scenarios-and-tools)。

## 缩小到的调用边界

第一版诊断内核在关键调用前后输出 `K53DIAG ... ENTER/RETURN`。录像显示
EFI `SetVirtualAddressMap` 及其后续处理已经返回，VFS 初始化也已完成。
之后的最后一组稳定标记为：

```text
M15 acpi_subsystem_init ENTER
A01 acpi_enable_subsystem ENTER
A03 read_original_acpi_mode ENTER
A03 read_original_acpi_mode RETURN
A04 acpi_enable ENTER
A07 set_acpi_mode ENTER
A08 SMI_ACPI_ENABLE_write ENTER
```

`A08` 包围的是 `acpi_hw_write_port()`，它还包含 I/O 请求验证，不能仅凭这段录像
断言实际 `outb` 指令或某条 SMM 内部指令是最终停止位置。第二版补充了原始端口
I/O 标记和提前启用 ACPI 的实验参数；用户随后确认提前启用项可以启动。

FADT 中的已验证布局：SMI_CMD=`0xB2`，ACPI_ENABLE=`0xA0`，PM1a_CNT=`0x404`。
这些是本项目严格匹配的寄存器值，不是面向其他硬件的通用配置。
ACPI 模式切换含义见 [ACPI 规范](https://uefi.org/specs/ACPI/6.5/05_ACPI_Software_Programming_Model.html)。

## 排除和未排除的内容

Legacy、UEFI/noruntime 和提前启用实验中导出的 16 个 ACPI 表文件逐字节相同。
有校验字段的表校验和均通过。资源冲突警告在可正常启动的环境中也存在。
因此没有证据支持直接替换 DSDT、添加 GOP，或把问题简单归为表校验损坏。

现有证据支持：**启用 ACPI 相对于 EFI 运行时初始化的先后顺序影响故障复现。**
Linux 的成功与 Windows 前置引导的成功一致。后续单槽位对照已将启动触发点定位到
SVAM 后的 ECProtocol +0x38 方法地址，详见[因果证据](root-cause-evidence.md)。
尚未证明所有系统版本及设备电源状态都能正常运行。

## 实现过程中的修正

- Shell 入口在实机黑屏，改用 ISO/GRUB 直接启动 EFI 程序。
- 早期只检查 `sources/boot.wim`，漏掉双架构安装盘的 `x64/sources/boot.wim`。
  v3 加入后者作为替代路径，仍启动同分区原版 `EFI/BOOT/BOOTX64.EFI`。
- 大量 `initcall_debug` 输出曾覆盖日志缓冲区中的早期标记。后续详细采集应增加
  `log_buf_len=8M`；不能声称那些已被覆盖的标记仍存在于成功启动的日志包中。

## 验证边界和后续工作

已验证的是安装环境启动，不是 BIOS 修复，也不是已安装 Windows 的长期使用。
当前程序只识别安装分区；持久入口需要单独选择硬盘上的 Windows Boot Manager，
保留原版引导与恢复路径。还需验证安装后冷启动、重启、关机、睡眠和唤醒。

BIOS/SPI 未被写入；原始固件、录像和机器日志仅保留在 Git 忽略的本地归档中。

## 后续定位

同镜像 PRE_SVAM 成功、POST_SVAM 冻结的对照见 [EFI 阶段结果](efi-stage-results.md)。
后续动态清单、EC WATCH 和单槽位干预将触发点定位到 ECProtocol +0x38 方法地址，
详见 [根因证据](root-cause-evidence.md)。

Windows 8.1 x64 的现场对照同样为直接 UEFI 启动冻结、AcpiFirst v3 后进入安装首页，
并报告 SCI_EN=1；该次没有提供启用前读数、对应录像/日志或安装 ISO 摘要。
这支持跨版本的绕过效果，但不能据此推断 Windows 的内部调用序列。
