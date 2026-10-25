# EFI/ACPI 机制与阶段探针设计依据

检索日期：2026-10-25。本文研究固件根因，不把可用的引导绕过等同于 BIOS 修复。

本文保留阶段探针设计时的证据和假设；后续结果见 [EFI 阶段对照](efi-stage-results.md)，当前定位见 [根因证据](root-cause-evidence.md)。

## 1. 探针设计前的实机证据

以下来自本项目的实机实验及已保存录像/日志，不是从通用规范推导出的硬件结论：

- 默认顺序在 `A08 SMI_ACPI_ENABLE_write ENTER` 后没有相应返回。
- `A08` 包围 `acpi_hw_write_port()`；仅凭该标记尚不能断言真正的 `outb` 指令未返回。
- EFI 地址转换及后续标记已经返回，不能称为 `SetVirtualAddressMap()` 当场卡死。
- `efi=noruntime` 可启动；将 ACPI_ENABLE 提前到 EFI 运行时初始化之前也可启动，并保留 EFI 运行时服务。
- EFI 前置程序提前启用 ACPI 后，原版 Windows 64 位安装环境可重复启动。
- Legacy 与成功的 UEFI 实验中导出的 16 个 ACPI 文件相同。此结果不能证明所有 AML 逻辑无误，但不支持“UEFI 产生另一份损坏 DSDT”的简单解释。

当时用于设计实验的问题是：**哪一步 EFI 运行时初始化改变了随后 ACPI 模式切换所依赖的固件状态？**

## 2. ACPI_ENABLE 请求的规范含义

FADT 的 `SMI_CMD` 给出命令端口，`ACPI_ENABLE` 给出启用值。操作系统从引导处理器同步发出请求，固件交接 ACPI 寄存器控制权，最后设置 `SCI_EN`。本机的 `0xB2`、`0xA0`、`PM1a_CNT=0x404` 来自实际 FADT，不能推广为所有机器通用值。[ACPI 规范：FADT 与 SMI_CMD](https://uefi.org/specs/ACPI/6.6/05_ACPI_Software_Programming_Model.html)

Linux 的 OS 端口实现对 8 位写入最终使用 `outb`。所以第二版诊断加入的指令前后标记，比外围 ACPICA 调用标记更接近硬件边界；需要原始基线录像来确认它的最后位置。[Linux v7.2 `drivers/acpi/osl.c`](https://raw.githubusercontent.com/torvalds/linux/v7.2/drivers/acpi/osl.c)

## 3. 必须拆开的 EFI 阶段

Linux 7.2.7 的 `__efi_enter_virtual_mode()` 在 `SetVirtualAddressMap` 成功返回后，还会处理 embedded firmware、调用 `efi_unmap_boot_services()`、设置原生/混合运行时入口、更新映射权限，并调用 `efi_delete_dummy_variable()`。因此“整个 EFI 阶段之后失败”不能直接归因于其中第一项。[Linux v7.2.7 `efi.c`](https://raw.githubusercontent.com/gregkh/linux/v7.2.7/arch/x86/platform/efi/efi.c)

### 关键控制变量：`efi=debug` 不只是多打印日志

已核对的 Linux v7.2.7 `efi_unmap_boot_services()` 开头有：

```c
if (efi_enabled(EFI_DBG))
    return;
```

这是为保留 EFI debugfs 区域而跳过处理。函数内部正常情况下会解除 EFI 专用页表中 boot-services 区域的映射、整理描述符，并排队待释放区域。真正的页释放由后面的 `arch_initcall(efi_free_boot_services)` 执行。两者不是同一时刻。[Linux v7.2.7 `quirks.c`](https://github.com/gregkh/linux/blob/v7.2.7/arch/x86/platform/efi/quirks.c)

**对本项目的影响：**失败诊断菜单带有 `efi=debug`。精确 7.2.7 源码已确认保留上述条件，因此 `E07 ENTER/RETURN` 仅表示进入又提前退出，不能声称做过 unmap；实际 free 又发生在更晚的 initcall 阶段。这显著降低“当前故障由 boot-services 内存已被解除映射或回收造成”的优先级。

版本核验：已进一步读取本次下载的精确 v7.2.7 `quirks.c`：第 424 行检查 EFI_DBG 并返回，第 108 行开始的 DUMMY helper 无条件调用 SetVariable，第 562 行注册较晚的释放 initcall。最初使用相邻 v7.2/master 的线索现已由精确版本确认。

### `DUMMY` 清理不是只读操作

`efi_delete_dummy_variable()` 会调用非阻塞 `SetVariable`，以零数据长度删除特定 GUID 下的 `DUMMY` 变量。这会进入变量服务实现；是否触发具体固件的垃圾收集或改变共享 SMI 状态，仍需验证。这个函数返回，不等于它没有留下影响后续请求的固件状态。[Linux v7.2.7 `quirks.c`](https://github.com/gregkh/linux/blob/v7.2.7/arch/x86/platform/efi/quirks.c)

`efi_no_storage_paranoia` 影响变量空间预留/检查策略，**不是**跳过该早期 `DUMMY` 调用的开关；上述 `efi.c` 调用点和 helper 本身没有检查这个参数。`efi=noruntime` 一次跳过的范围则过大，不能把它当作仅禁用变量清理的对照。不要为了本次实验使用“强制变量垃圾收集”之类无关设置。[Linux v7.2.7 调用点](https://raw.githubusercontent.com/gregkh/linux/v7.2.7/arch/x86/platform/efi/efi.c)、[Linux v7.2.7 参数实现](https://github.com/gregkh/linux/blob/v7.2.7/arch/x86/platform/efi/quirks.c)

## 4. 地址转换与 SMM 的规范背景

UEFI 的 `SetVirtualAddressMap()` 不只是安装页表：规范要求在返回之前通知虚拟地址变化事件，并处理运行时组件与相关指针转换。成功返回意味着该调用结束，不意味着一个有缺陷的转换回调没有改坏供后续使用的数据。[UEFI 2.9：Runtime Services / SetVirtualAddressMap](https://uefi.org/sites/default/files/resources/UEFI_Spec_2_9_2021_03_18.pdf)

EDK2 的 Runtime DXE 参考实现依次通知事件、重定位运行时映像、转换运行时服务表入口并更新表校验。它说明这种延迟暴露的失效机制是可检查的，但不证明 AMI Aptio 采用相同代码。[EDK2 `Runtime.c`](https://github.com/tianocore/edk2/blob/master/MdeModulePkg/Core/RuntimeDxe/Runtime.c)

SMM 相关结构要区分 DXE/运行时调用者使用的指针与 SMM 消费的物理地址或缓冲区约定。EDK2 SMM IPL 明确处理运行时地址转换，并在现代通信接口中区分 physical/virtual buffer。其当前回调实现只转换 `mSmmControl2`；附近注释提到其他对象，不能把注释当作所有实际转换列表。不能据此断言“本机 SMM 直接用了 OS 虚拟地址”，更不能断言 SMM 永远没有自己的页表。[EDK2 `PiSmmIpl.c`](https://github.com/tianocore/edk2/blob/master/MdeModulePkg/Core/PiSmmCore/PiSmmIpl.c)

## 5. 阶段实验前的候选假设

| 优先级 | 当时的假设 | 最小预测与区分方式 |
| --- | --- | --- |
| 高 | SVAM 或其事件回调/重定位改变了 ACPI SMI 处理依赖的地址或共享状态 | 同一内核中，SVAM 前的单次 ACPI_ENABLE 成功，SVAM 刚返回、任何后续 helper 之前的同一请求失败；若后者成功，此解释作为唯一原因被削弱。 |
| 高 | 第一次转换后的变量服务调用影响共享 SMI 状态，或留下错误的锁/通信上下文 | 保留完整 SVAM 与映射处理，仅跳过早期 `efi_delete_dummy_variable()` 后默认 ACPI 时机可启动；或 DUMMY 前探针成功、DUMMY 后探针失败。成功也只能定位到该调用造成的状态变化，不能直接断言 GC 是根因。 |
| 中 | 后续运行时入口设置或映射权限处理改变了故障条件 | SVAM 刚返回的请求成功，`efi_runtime_update_mappings()` 后、DUMMY 前的请求失败。需要继续拆分该区间；OS EFI 页表改变并不自动等于 SMM 页表也改变。 |
| 低 | boot-services 区域 unmap/free 破坏固件仍在依赖的内容 | 精确 7.2.7 已确认带 `efi=debug` 时函数提前返回。此条件下仍失败，该路径不是当前失败的充分解释；实际 free 的较晚调用时机也不吻合。 |
| 先决边界 | 现有 A08 停止其实在请求验证、真正 I/O 之后的另一事件，或输出可见性边界 | 取得默认顺序下 `IO outb port=0xb2 value=0xa0 ENTER/RETURN` 与后续 SCI_EN 读出的记录。若根本没有 IO ENTER，应先查外围验证；若 IO RETURN 已有，不能再说 outb/SMI 未返回。 |

## 6. 阶段探针设计

先补足真正端口 I/O 的默认基线，再在**同一个诊断内核**中用一个选择参数指定唯一 ACPI 启用位置：

1. `pre_svam`：EFI 页表准备完成、实际 SVAM 调用之前。
2. `post_svam`：SVAM 成功返回的错误检查之后、embedded-firmware/helper 之前。
3. `pre_dummy`：运行时入口和权限更新完成，DUMMY 清理之前。
4. `post_dummy`：DUMMY 调用返回之后。

每次启动只能选择一个位置执行一次。前面若已设置 SCI_EN，后面的 `acpi_enable()` 会走“已启用”分支；把四个请求放在一次启动里将无法形成有效对照。保留无探针的原顺序基线与已知成功的早启对照，统一 `efi=debug`、工具链和其余配置，增加 `log_buf_len=8M` 防止日志覆盖。

如果只希望先做一个改动，**跳过唯一的早期 DUMMY 删除调用**比继续尝试宽泛内核参数更有区分度；要在菜单和日志中明确标注“此处跳过”，不把它叫修复。它只是省去一次已有的变量服务调用，不应新增变量写入、清空 NVRAM 或改写固件。

阶段定位之后再结合原始 BIOS 静态分析，追踪相应地址变化事件回调、共享对象和 ACPI SMI handler。没有准确硬件阶段证据前，不能仅凭模块名或 GUID 推断需要刷写哪个模块。


## 7. UEFI 版本背景

Windows 支持、OEM 认证与 Secure Boot 的版本门槛见 [UEFI 版本与 Windows 8](uefi-versions-windows8.md)。
本机提前启用实验没有升级 UEFI 实现或修改 revision 字段；版本数字本身不能解释这个故障。
