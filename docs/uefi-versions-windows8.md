# UEFI 2.0、2.3.1 与 Windows 8

核查日期：2026-10-25。以下区分操作系统支持、OEM 认证和具体功能，不能用版本标签代替实现验证。

## Windows 8 的原始要求

微软 2014-03-06 的 [UEFI Firmware 文档](https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-8.1-and-8/hh824898(v=win.10)) 明确写出：

- Windows 8/8.1 支持 x86、x64、ARM 上原生 UEFI 2.0 或更新版本。
- Secure Boot 等功能要求 UEFI 2.3.1 Errata C 或更高版本。
- UEFI 模式下 Windows/WinPE 架构必须与固件匹配；x64 固件不能直接启动 x86 Windows。
- Windows 使用规范功能的子集，不显式检查更高固件修订版本。
- UEFI 安装目标系统盘采用 GPT；这不是对所有安装 U 盘分区表的要求。

[Windows 8/8.1 硬件认证要求](https://download.microsoft.com/download/7/0/e/70e74967-b0fe-477a-974f-c1ed16ee31df/windows8-1-hardware-cert-requirements-system.pdf) 的 System.Fundamentals.Firmware.UEFICompatibility 要求兼容 UEFI 2.3.1 的指定章节，并要求客户端默认 UEFI 启动、认证时不启用 CSM。这是认证条件，不能直接推成旧电脑的安装程序必须拒绝 UEFI 2.0。

## 与故障相关的规范差异

以下为选取的变更，不是完整差异列表。[UEFI 官方修订历史](https://uefi.org/specs/UEFI/2.10/Frontmatter/Revision_History.html) 保留了这些早期版本条目：

| 范围 | 具体变化 | 对本机的意义 |
| --- | --- | --- |
| 启动交接 | 2.2，M347：替换 ExitBootServices 描述的首段 | 应核查实际交接行为，不能只检查 revision |
| 固件变量 | 2.3.1，M711/M724：SetVariable 更新；M679：认证变量及签名数据库更新 | 普通变量调用与安全认证变量不能混为一谈；现有 skip-DUMMY 实验只隔离一个实际调用 |
| SMM | 2.3.1，M736：加入 SMM Communication ACPI 表及相关结构 | 不等于旧固件不能响应 ACPI_ENABLE 软件 SMI，也未证明本机需要此表 |
| 安全启动 | 2.3.1，M734：SecureBoot 变量及相关安全机制完善 | 不启用 Secure Boot 时，缺少此功能不能单独解释当前冻结 |
| 外设 | 2.2 的 IPv6/ATA Pass-Through；2.3.1 的 USB 3.0、非阻塞 Block I/O | 是真实功能差异，但与目前 ACPI 启用卡点的关系尚无证据 |

2.3.1C 还增加了 OsIndications，用于 OS 与固件沟通功能请求（如下一次重启进入设置），并调整密钥管理和 UNDI 要求。见 [UEFI Forum 2012 公告](https://uefi.org/press-release/UEFI_Forum_Releases_UEFI_2.3.1_Specification_Update_and_Schedules_July_3_2012)。不能把 C 的所有变化都归到 2011 年初版 2.3.1。

## 当前研究判断

AcpiFirst 未升级 UEFI 实现却能重复进入 x64 安装程序，反对“版本数字低，所以无条件不能启动”的解释；但并不排除旧实现存在后来规范澄清的行为问题。

后续实机对照和单槽位干预已将本次触发点定位到 SVAM 后的 ECProtocol 方法地址，
见 [根因证据](root-cause-evidence.md)。版本差异提供规范背景，不能替代该硬件证据。
