# EFI 阶段对照结果

2026-10-25，在同一 K53SJ / BIOS 315 诊断镜像上比较 ACPI_ENABLE 的调用时机。
构建、菜单和复现方法见 [阶段探针](../research/linux/STAGE3.md)。

| 对照 | 结果 | 证据边界 |
| --- | --- | --- |
| BASELINE | 冻结 | 照片最后为 outb ENTER，未见 RETURN |
| skip-DUMMY | 冻结 | 菜单身份来自现场报告，照片未独立证明跳过分支 |
| POST_SVAM | 冻结 | SCI_EN=0，SVAM 已返回，未见 outb RETURN |
| PRE_SVAM | 启动成功 | 日志确认 SCI_EN 由 0 变为 1，后续 SVAM/DUMMY 返回 |

这组结果把调查范围缩小到 SVAM 及其产生的固件状态变化。
后续方法指针与单槽位实验见 [根因证据](root-cause-evidence.md)。

## BASELINE 已复现

用户提供第 6 项照片：M15 acpi_subsystem_init ENTER 后依次出现 A01、A03 ENTER/RETURN、
A04、A07、A08，最后可见：

```text
[5.419556] ACPI: OSL: K53DIAG IO outb port=0xb2 value=0xa0 width=8 ENTER
```

照片未见对应 IO RETURN，用户报告此为停止画面。证据推进到实际 outb 前日志边界，
不再仅停留在 ACPICA 参数验证外围。但单张照片不能证明 CPU 已执行该指令或精确
定位 SMM 内部函数，也不能排除日志输出本身的可见性边界。

## skip-DUMMY 仍冻结

用户随后提供第 1 项照片：同样经过 M15/A01/A03/A04/A07/A08，最后为
`[4.482486] ACPI: OSL: K53DIAG IO outb port=0xb2 value=0xa0 width=8 ENTER`，
未见 IO RETURN。用户将照片标记为第 1 项 skip-DUMMY；当前照片不包含较早的
`K53PHASE DUMMY_DELETE SKIPPED` 或完整 cmdline，故菜单身份来自用户报告，
跳过分支本身尚未由该真机照片独立确认。

在菜单确实执行预期跳过分支的前提下，DUMMY 删除不是复现故障的必要条件。

## POST_SVAM 仍冻结

用户提供第 2 项照片，关键顺序如下：

```text
[6.006839] efi: K53DIAG E05 SetVirtualAddressMap ENTER
[6.007902] efi: K53DIAG E05 SetVirtualAddressMap RETURN
[6.009839] efi: K53DIAG E06 embedded_firmwares ENTER
[6.010839] efi: K53PHASE POST_SVAM ENTER EFI_DBG=1
[6.011843] efi: K53PHASE POST_SVAM BEFORE SCI_EN=0 sci_status=0x0
[6.012842] K53DIAG A07 set_acpi_mode ENTER
[6.014839] K53DIAG A08 SMI_ACPI_ENABLE_write ENTER
[6.016839] ACPI: OSL: K53DIAG IO outb port=0xb2 value=0xa0 width=8 ENTER
```

未见 IO RETURN 或 POST_SVAM RETURN。该探针位于 SVAM 成功返回检查之后、
efi_check_for_embedded_firmwares() 实际调用之前；E06 ENTER 是外层先输出的标记，
不能据其出现声称 embedded-firmware helper 已执行。此时尚未执行后续运行时权限
更新和 DUMMY 删除，二者不是本次探针失败的必要条件。

## PRE_SVAM 成功（已核对日志包）

成功启动日志包为 k53diag.tar.gz；本地证据副本为
`local/evidence/stage3-pre-svam.tar.gz`（Git 忽略）。cmdline 明确为
`k53diag_acpi_phase=pre_svam`，无 acpi=off、efi=noruntime 或 skip-DUMMY。

```text
[6.151189] K53PHASE PRE_SVAM ENTER EFI_DBG=1
[6.153193] K53PHASE PRE_SVAM BEFORE SCI_EN=0 sci_status=0x0
[6.158189] K53DIAG IO outb port=0xb2 value=0xa0 width=8 ENTER
[6.161188] K53DIAG IO outb port=0xb2 RETURN
[6.166193] K53PHASE PRE_SVAM RETURN acpi_status=0x0 SCI_EN=1 sci_status=0x0
[6.167189] K53DIAG E05 SetVirtualAddressMap ENTER
[6.168254] K53DIAG E05 SetVirtualAddressMap RETURN
[6.181189] K53DIAG E09 delete_dummy_variable ENTER
[6.184190] K53DIAG E09 delete_dummy_variable RETURN
[6.302188] K53DIAG M15 acpi_subsystem_init RETURN
[10.407190] efivars: Registered efivars operations
```

与同镜像 POST_SVAM 照片形成关键对照：两次请求前 SCI_EN 都为 0；转换前请求返回并
置 1，转换后请求未见 RETURN。优先调查范围现在是 SVAM 调用期间/调用上下文及其
产生的固件状态变化，不再优先拆分之后的权限更新或 DUMMY。
这不是证明某个虚拟指针错误：仍需区分地址转换通知、映像重定位、固件自身状态分支
及调用前后执行环境差异。成功路径中后续 SVAM/DUMMY 均返回，也说明提前启用后
不需要整体关闭 EFI 运行时。尚未在已启用状态下再次强制触发 ACPI_ENABLE，不据此
宣称 SMI 本身在转换后恢复。禁止为取样主动切回传统 ACPI 模式。
