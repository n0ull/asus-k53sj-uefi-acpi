# AcpiFirst — ASUS K53SJ UEFI 启动冻结定位与绕过

UEFI boot-freeze investigation and an experimental early-ACPI chainloader for the ASUS K53SJ.

在 **ASUS K53SJ / BIOS 315 / 64 位 UEFI** 上，Linux 默认启动冻结，Windows 安装环境在最初转圈时冻结。本项目通过阶段探针、固件静态分析、运行时地址采样和单槽位干预，定位了 Linux 路径中的故障触发机制，并验证了提前启用 ACPI 的启动绕过。

**原因定位已完成，研究止于解释故障，不继续制作永久固件修复。** AcpiFirst v3 在启动原版 Windows EFI 引导器之前请求固件启用 ACPI，已在这台实体机上重复进入 64 位 Windows 安装程序。

## 故障机制与启动链

固件的 `ECProtocol` 发布 EC（嵌入式控制器）方法表，`AcpiModeEnable` 保存公开协议表指针。EFI 运行时地址转换 `SetVirtualAddressMap`（SVAM）之后，表内方法地址变为操作系统虚拟地址；后续 ACPI 启用的 SMM 回调仍通过这张表调用方法，出现地址使用域不匹配。

已诊断的 Linux 启动路径如下：

```text
UEFI 初始化 ECProtocol，AcpiModeEnable 保存公开表指针
    ↓
引导器启动 Linux，结束 Boot Services
    ↓
Linux 初始化 EFI runtime，调用 SetVirtualAddressMap
    ↓
ECProtocol 表内方法地址由物理地址转换为 OS 虚拟地址
    ↓
ACPI 初始化发现 SCI_EN=0，向端口 0xB2 写入 0xA0
    ↓
固件处理软件 SMI，AcpiModeEnable 经 [table+0x38] 调用 EC 方法
    ↓
该槽内的虚拟地址不适用于此调用环境，ACPI_ENABLE 请求不返回
```

支持这一定位的关键证据：

- **阶段对照**：同一诊断镜像中，SVAM 前启用 ACPI 成功，SVAM 后启用冻结；失败路径中 SVAM 本身已经返回。
- **地址采样**：EC WATCH 确认同一物理表的前 9 个方法槽均在 SVAM 后变为预期虚拟地址。
- **静态调用链**：ACPI 启用回调在模块 RVA `0x53A` 调用 `[table+0x38]`，对应 ECProtocol 方法 RVA `0xE74`。
- **单变量干预**：仅在 ACPI_ENABLE 请求期间将 `+0x38` 恢复为原物理地址，请求就能返回、`SCI_EN` 变为 1；随后恢复虚拟地址，系统继续启动。没有关闭 ACPI 或 EFI runtime。

这已形成故障触发点的因果证据。**具体 CPU 异常类型和最后失败指令未直接观测**：没有 SMM 指令级跟踪，不能把冻结直接称为已确认的页故障。Windows 经前置启用成功与上述机制一致，但其内部调用栈没有直接采样。

详见 [单槽位因果证据](docs/root-cause-evidence.md)、[EFI 阶段对照](docs/efi-stage-results.md)及 [DXE/SMM 消费者分析](docs/ec-smm-consumer-analysis.md)。

## AcpiFirst 的绕过方式

```text
UEFI → Ventoy/GRUB → AcpiFirst.efi
    → 在 SVAM 前启用 ACPI，确认 SCI_EN=1
    → 启动原版 Windows EFI 引导器
```

提前启用时，方法表仍含物理地址。已验证的 Linux 提前启用路径随后发现 ACPI 已启用，不再发出同一次模式切换请求；Windows 安装环境的成功结果也支持这一绕过方式。

AcpiFirst 是安装介质的前置引导程序。已安装系统的长期稳定性，以及睡眠、唤醒等电源状态未验证。

## 当前功能

- 核对 SMBIOS 的 K53SJ 机型与已验证的 FADT 寄存器布局。
- 查找唯一的、固件可读取的 Windows 安装分区，支持两种安装介质布局。
- 加载该分区原版 `\EFI\BOOT\BOOTX64.EFI`。
- 必要时向 SMI_CMD `0xB2` 写入 ACPI_ENABLE `0xA0`，确认 SCI_EN 后启动原版引导器。
- 没有新增磁盘写入、EFI 启动变量修改或刷 BIOS 操作。原版 Windows 引导器继续执行自身正常行为。

当前只支持**安装介质**，尚未实现指向硬盘已安装 Windows 的持久引导入口。32 位 Windows 不适用这条 64 位 UEFI 引导链。

## 构建

已测试 Ubuntu 24.04 x86-64（包括 WSL2）。依赖：

```sh
sudo apt-get update
sudo apt-get install --no-install-recommends \
  build-essential python3 gnu-efi grub-pc-bin grub-efi-amd64-bin \
  xorriso mtools
make test
make build
```

输出位于 `build/dist/`：

```text
AcpiFirst.efi
AcpiFirst-Direct-v3-UEFI.iso
SHA256SUMS
```

路径从仓库位置推导，不依赖开发者本机目录或 BIOS 转储。可设置 `BUILD_DIR` 改变输出目录，或用 `GNU_EFI_INCLUDE`、`GNU_EFI_LIBDIR` 指定 GNU-EFI 的安装位置。构建会在产物目录中附带项目及第三方许可文本。

## 使用

1. 将生成的 ISO 复制到 Ventoy U 盘。
2. 另插一只已经制作好的、固件可读取的 Windows 64 位安装 U 盘。
3. 使用 **UEFI → 该 ISO → Normal mode** 启动，选择菜单中的 AcpiFirst。
4. 记录最后提示以及 Windows 是否进入安装界面。验证启动只需到达安装界面，不需要更改硬盘分区。

安装分区必须同时包含：

```text
\EFI\BOOT\BOOTX64.EFI
\sources\boot.wim        或 \x64\sources\boot.wim
```

只有存放在 Ventoy 上、尚未作为安装文件系统暴露的 Windows ISO 文件不满足查找条件。找不到安装盘或找到多块时，程序会停止，不会自动选择其他系统。

无需 BIOS 内置 Shell，也无需外部 EFI Shell。

## 测试

```sh
sudo apt-get install --no-install-recommends qemu-system-x86 ovmf
make vm-test
```

测试覆盖 FADT 校验及布局拒绝、SMBIOS 字符串边界、UEFI 程序入口，以及零个/一个/多个/双架构安装分区的识别。使用生成的假安装文件和临时虚拟磁盘，不接入宿主磁盘；查找测试程序不执行 SMI 写入或启动 Windows。

OVMF 测试验证程序和拒绝条件，不能模拟本机固件故障。`make test` 覆盖核心表解析、单槽位保护及运行时映像匹配。实机对照与验证范围见 [诊断记录](docs/investigation.md)。

## 仓库结构

```text
src/                当前 EFI 程序与平台表解析
boot/               无需 Shell 的 GRUB 入口
scripts/            可移植构建和测试脚本
tests/              合成表测试与隔离 UEFI 虚拟机测试
docs/               实验结论和开发说明
research/linux/     Linux 7.2.7 诊断补丁、配置及采集环境
LICENSES/           第三方许可文本
build/              生成产物（Git 忽略）
```

原始 BIOS、Windows 文件、机器日志、录像和生成二进制不纳入源码历史。需要分享二进制时，可将 `build/dist/` 中的产物及许可文件作为单独的 Release 附件。

全部研究记录见 [文档导航](docs/README.md)。`make test` 不需要私有固件或虚拟机。

## 许可

新增 EFI 程序、脚本及原创文档采用 [MIT](LICENSE)。Linux 诊断补丁与第三方组件不因此改为 MIT；范围及上游信息见 [第三方说明](THIRD_PARTY_NOTICES.md)。
