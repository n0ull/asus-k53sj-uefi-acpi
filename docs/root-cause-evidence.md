# 启动冻结的单槽位因果定位

日期：2026-10-25。机器为 ASUS K53SJ、BIOS 315、x64 UEFI。

## 当前结论

在本机 Linux 诊断启动路径中，**SVAM 后的 ECProtocol +0x38 方法地址是已验证的
故障触发点**：保留 EFI 地址转换及其余初始化，仅在 ACPI_ENABLE 请求期间将这个
槽位恢复为原物理地址，请求便正常返回；之后恢复预期虚拟地址，系统仍继续启动。

结合 AcpiModeEnable 中对共享 EC 协议 +0x38 的间接调用，证据高度支持固件在
SMM/EFI runtime 之间共享方法表时未正确处理物理与虚拟地址使用域。这不是普通的
“UEFI 版本号不够”或 DSDT 校验失败，也不要求关闭全部 ACPI/EFI runtime。

这里的因果定位不等于已获得 SMM 指令级跟踪：没有直接读取本次 SMRAM 实例的
保存指针，也没有记录最后一条执行失败的 CPU 指令。仍应把这两点与已经证明的
单槽位效果分开，而不是宣称完成了完整固件源码审计。

## 输入与基线

用户提供 38.tar.gz，50,471 字节，SHA256：
`ee659312369c349a6e4138ea28d2eabb262a5b290cdd0e21d2a46d9ee3660032`。
证据副本在 Git 忽略目录 `local/evidence/ec-slot38-success.tar.gz`。

同次反馈附带的照片未出现 APPLY，显示同镜像基线在 SCI_EN=0、ACPI_ENABLE
outb ENTER 后停止。成功日志 cmdline 则明确包含 `k53diag_ec_restore38` 和
`k53diag_acpi_phase=post_svam`，没有 acpi=off 或 efi=noruntime。

## 成功日志的完整关键链

```text
K53EC PRE candidates=1 pages=201 base=0xaad49000
SetVirtualAddressMap RETURN
K53EC POST physical_table=0xaad4ae70 changed=9 translated=9/9
K53SLOT38 APPLY ENTER addr=0xaad4aea8
    old=0xfffffffef6949e74 new=0xaad49e74 RAM_ONLY
K53SLOT38 APPLY RETURN readback=0xaad49e74 match=1
K53PHASE POST_SVAM BEFORE SCI_EN=0 sci_status=0x0
K53DIAG IO outb port=0xb2 value=0xa0 width=8 ENTER
K53DIAG IO outb port=0xb2 RETURN
K53PHASE POST_SVAM RETURN acpi_status=0x0 SCI_EN=1 sci_status=0x0
K53SLOT38 CLEANUP ENTER addr=0xaad4aea8
    old=0xaad49e74 new=0xfffffffef6949e74 RAM_ONLY
K53SLOT38 CLEANUP RETURN readback=0xfffffffef6949e74 match=1
E09 delete_dummy_variable RETURN
M15 acpi_subsystem_init RETURN
efivars: Registered efivars operations
```

地址只属于这次启动。程序通过唯一映像匹配和九槽校验得到它们，不硬编码绝对地址。
单槽实验实际仅写入 +0x38，并在请求之后恢复；+0x40 和其他方法槽未改动。

## 为什么 AcpiFirst 有效

在 SVAM 之前，方法表仍含物理方法地址，ACPI_ENABLE 能正常完成。提前把 SCI_EN
置为 1 后，操作系统后续发现 ACPI 已启用，不再走同一次模式切换请求。Windows
8.1 与较新版 Windows 安装程序经前置启用成功，与此机制一致。
Windows 内部调用序列没有通过本轮内核探针直接采样，因此不能声称其执行了 Linux
的具体 helper 或具备完全相同的调用栈。

## 306 对照及剩余边界

- 306/315 的 ECProtocol 与 AcpiModeEnable 的 .text/.data/.reloc 完全相同；设计早已
  存在，不能将原因简单定为 315 新增方法代码。306 的真机行为尚未验证。
- EC 控制器载荷候选和 DSDT 等有变化；未证明某个版本降级能修复或完整恢复 EC 状态。
- 当前完成的是启动故障触发点定位，不是长期修复验收。其他 SMM EC 方法、睡眠、
  唤醒、重启与关机仍未验证；临时实验镜像不作为日常引导工具。
- 未刷 BIOS、未修改 NVRAM；本轮成功的 RAM 写入已经回读确认清理。

## 后续静态消费者审查

完整生产者和消费者审查已确认：DXE 公开协议与 AC SMM 配置表发布相同 RVA、
相同布局的 37 槽方法表；旧版 SMM Base 会另行加载 SMRAM 实例，因此相同 RVA
不等于同一运行时物理表。AcpiModeEnable 保存公开表指针，其 SMI 回调在
RVA `0x53A` 经 `+0x38` 间接调用，和本次单槽干预精确对应。
NBFSMM 与 ASUSVGASMI 使用 AC SMM 配置表，现有证据不支持把它们列为本次
SVAM 故障面。详见 [DXE/SMM 共享表与消费者审查](ec-smm-consumer-analysis.md)。
本项目以原因定位为终点，不继续制作永久固件修复。
