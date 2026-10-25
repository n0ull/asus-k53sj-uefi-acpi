# ECProtocol 的 DXE/SMM 共享表与消费者审查

日期：2026-10-25。对象仍为 ASUS K53SJ BIOS 315，输入 SHA256 为
`126ee0fa737e35071a4f383b7e1be1579f1e069755bdc6379d96ee3f3b90f8f8`。
本轮只读分析本地提取的 PE，没有执行、修改或刷写固件。

## 结论

1. ECProtocol 在 DXE 公开协议和 SMM 配置表两条发布路径中使用**相同 RVA 和
   布局的方法表**：模块 RVA `0x1E70`，长度 `0x128`。它不是前 9 槽加未知尾部，
   而是完整的 **37 个 64 位方法指针**；所有目标都落在本模块有效 `.text` 中。
   旧版 SMM Base 会把驱动另行加载到 SMRAM，因此相同 RVA 不等于两个运行时
   物理实例共用地址。
2. AcpiModeEnable 在入口通过 DXE `LocateProtocol` 保存公开表指针，ACPI_ENABLE
   的 SMI 回调随后在 RVA `0x53A` 执行 `call [table+0x38]`。AcpiModeEnable 不在
   已采集的 Runtime 映像转换清单中，而 ECProtocol 是 Runtime 驱动；这与“消费者
   继续按物理表取方法、表内方法值却被 SVAM 改成虚拟地址”的机制一致。
3. slot38 单槽真机干预已经证明：把这个调用将读取的 `+0x38` 方法值临时恢复为
   物理地址后，同一 ACPI_ENABLE 请求返回。静态调用链、生产者发布方式和动态干预
   因而在同一条路径上闭合。
4. NBFSMM 和 ASUSVGASMI 使用 AC SMM 配置表中的多个其他槽位。现有证据不支持
   把这张 SMM 表也列为已转换或已故障的对象；没有 SMRAM 动态采样，必须保留
   DXE/SMM 实例边界。当前修复目标应限于 AcpiModeEnable 的公开表使用方式。
## ABI 与发布路径

旧版 `EFI_SMM_BASE_PROTOCOL` 的方法顺序与本机调用相符：`+0x20` 是 `InSmm`，
`+0x38` 是 `GetSmstLocation`。旧版 Framework SMST 的 x64 布局中，`+0x28` 是
`SmmInstallConfigurationTable`，参数为 `(SMST, GUID, Table, TableSize)`；
`+0xA8/+0xB0` 分别是配置项数量和数组。主源参考：

- [EDK2 IntelFrameworkPkg SmmBase.h](https://git.ti.com/cgit/uefi/ti-edk2/plain/IntelFrameworkPkg/Include/Protocol/SmmBase.h)
- [EDK2 IntelFrameworkPkg Framework/SmmCis.h](https://git.ti.com/cgit/uefi/ti-edk2/plain/IntelFrameworkPkg/Include/Framework/SmmCis.h)
- [旧版 SMM CPU I/O 布局](https://git.ti.com/cgit/uefi/ti-edk2/plain/IntelFrameworkPkg/Include/Protocol/SmmCpuIo.h)

ECProtocol 的 RVA `0x76C` helper 先定位 SMM Base 并检查 `InSmm`，再分别选择：

| 路径 | 实际行为 |
| --- | --- |
| DXE，回调 RVA `0x2A0` | 经 BootServices `+0x80` 的 `InstallProtocolInterface`，以 GUID `34CF7EC3-50F4-4544-8F50-FB1F9FF60748` 发布 RVA `0x1E70` |
| SMM，回调 RVA `0x2D4` | 经 SMST `+0x28`，以 GUID `AC44520D-0169-4966-B743-4F6CEAF2598E` 发布同一 RVA `0x1E70`，长度 `0x128` |

RVA `0x2D4` 的参数完全对应 `(gSmst, &GUID_1E30, &Table_1E70, 0x128)`。
所以“可能存在 SMM 配置表”已核实为事实；两个 GUID 是本固件私有 EC 接口标识，
本轮没有找到可用于命名 37 个方法的公开结构定义。

这里的“相同 RVA”只描述同一静态映像布局。SMM Base `Register` 会把驱动另行
加载到 SMRAM，ECProtocol RVA `0x694` 正使用这一服务；因此高置信度模型是
DXE Runtime 与 SMM 各有物理实例。没有直接读取 SMRAM，不能宣称已经测得两个
实例的地址关系，也不能把公开 Runtime 表的转换结果自动套到 AC SMM 表。

## 完整方法表

下表的“目标 RVA”由静态 preferred address 减去 ImageBase `0x140000000` 得到。
槽号从 0 开始。机器可读结果保存在忽略目录
`local/firmware-analysis/ec-review-2026-10-25/ec-table.json`。

| 槽 | 表偏移 | 目标 RVA | 槽 | 表偏移 | 目标 RVA |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | +0x000 | 0x0B4C | 19 | +0x098 | 0x1490 |
| 1 | +0x008 | 0x0C00 | 20 | +0x0A0 | 0x15C4 |
| 2 | +0x010 | 0x0C24 | 21 | +0x0A8 | 0x1804 |
| 3 | +0x018 | 0x0C4C | 22 | +0x0B0 | 0x15D0 |
| 4 | +0x020 | 0x0C68 | 23 | +0x0B8 | 0x161C |
| 5 | +0x028 | 0x0CC8 | 24 | +0x0C0 | 0x1668 |
| 6 | +0x030 | 0x0D44 | 25 | +0x0C8 | 0x16B4 |
| 7 | +0x038 | 0x0E74 | 26 | +0x0D0 | 0x173C |
| 8 | +0x040 | 0x0ED4 | 27 | +0x0D8 | 0x175C |
| 9 | +0x048 | 0x0F98 | 28 | +0x0E0 | 0x17BC |
| 10 | +0x050 | 0x1028 | 29 | +0x0E8 | 0x1A78 |
| 11 | +0x058 | 0x10B8 | 30 | +0x0F0 | 0x1978 |
| 12 | +0x060 | 0x1150 | 31 | +0x0F8 | 0x189C |
| 13 | +0x068 | 0x11E8 | 32 | +0x100 | 0x1568 |
| 14 | +0x070 | 0x12B0 | 33 | +0x108 | 0x1570 |
| 15 | +0x078 | 0x1368 | 34 | +0x110 | 0x1B18 |
| 16 | +0x080 | 0x13A8 | 35 | +0x118 | 0x1BEC |
| 17 | +0x088 | 0x13B4 | 36 | +0x120 | 0x0F34 |
| 18 | +0x090 | 0x1428 |  |  |  |

ECProtocol 的 DIR64 重定位项连续覆盖 RVA `0x1E70` 至 `0x1F90`，即全部
37 槽。Runtime RVA `0x1498` 的重定位器遍历这些项目并加上地址差。真机 EC WATCH
只逐个读取了前 9 槽并确认全部转换；后 28 槽具有相同静态重定位条件，但没有被
逐个真机采样，不能把这一点写成“37 槽均已实测”。

## 本次启动故障的完整数据流

1. AcpiModeEnable 入口 RVA `0x870` 在 `0x8C5` 调用 BootServices
   `LocateProtocol`，GUID 为公开 EC GUID，接口指针保存到全局 RVA `0x1158`。
2. ACPI_ENABLE 回调 RVA `0x474` 在 `0x52E` 读取这个全局指针；若为非零，
   RVA `0x53A` 调用 `[table+0x38]`。配对 ACPI_DISABLE 回调在 RVA `0x5C8`
   调用 `[table+0x40]`。
3. 表 `+0x38` 的静态目标是 ECProtocol RVA `0xE74`。因此 slot38 实验改变的
   正是这条间接调用将取得的目标，不是任意选择的无关数据。
4. AcpiModeEnable 是 EFI boot-service driver，且不在真机 RuntimeInventory 的
   22 个 Runtime 映像中；ECProtocol 则唯一匹配 Runtime 映像 RVA `0x2F8`。
   这支持消费者保存的表地址保持物理值，而 ECProtocol 表内 DIR64 项被转换。
5. 动态 slot38 对照满足 APPLY、`outb RETURN`、`SCI_EN=1` 和 CLEANUP 全部判据。

据此可以把**本机 Linux 启动冻结机制**表述为：SVAM 后，AcpiModeEnable 的 SMM
回调仍从物理共享表读取 `+0x38`，但该槽已含 OS 虚拟方法地址，导致 RVA `0x53A`
的间接调用失效。没有 SMM 指令级 CPU 跟踪，所以“CPU 最后停在何条指令”仍不是
直接观测；这不影响上述数据流与单变量因果结论。

## 消费者审查

### SMM 或 SMI 回调路径

| 模块 | 获取方式与保存位置 | 已确认调用槽及调用指令 RVA |
| --- | --- | --- |
| AcpiModeEnable | DXE 公开 EC GUID，保存于 `0x1158`，后续 SMI 回调使用 | `+0x38`：`0x53A`；`+0x40`：`0x5C8` |
| NBFSMM | SMM 配置 GUID，经通用 SMST 查找函数 `0xA24`，保存于 `0x16B8` | `+0x28`：`0x6C6`；`+0x60`：`0x509/0x51E/0x533/0x548`；`+0x88`：`0x342/0x367/0x38C/0x3BA`；`+0x90`：`0x3D6`；`+0x98`：`0x42B` |
| ASUSVGASMI | SMM 配置 GUID，经查找函数 `0x189C`，返回值仅留在 RAX | `+0x100`：`0x17AD` |

NBFSMM 和 ASUSVGASMI 的查找函数都遍历 `SMST+0xB0` 的配置项，按 `0x18`
步长比较 16 字节 GUID，命中后返回配置项 `+0x10` 的 `VendorTable`。
这与 ECProtocol 的 SMM 发布路径构成明确的生产者/消费者关系。

### DXE 公开协议路径

| 模块 | 协议指针保存位置 | 已确认 EC 调用槽及调用指令 RVA |
| --- | ---: | --- |
| ASUSPolicy | `0x1648` | `+0x60`：`0xBF0` |
| ASUSSetup | `0x8C18` | `+0x30`：`0x107F` |
| CougarPoint RC | `0x4C58` | `+0x120`：`0x230C` |
| ITEDXE | `0x0CE8` | `+0xE8`：`0x3F8`；`+0x20`：`0x406`；`+0x40`：`0x411`；`+0x98`：`0x421`；`+0x90`：`0x496` |
| NBFDxe | `0x0E78` | `+0x88`：`0x2EB/0x2FF`；`+0xB0`：`0x331`；`+0xB8`：`0x348`；`+0xC0`：`0x35F` |

这些调用位于 DXE 入口、协议通知或 Boot Services 事件上下文。不能仅凭模块中
存在 SMM Base GUID 常量便把调用归为 SMM：本轮直接解码确认五个模块中确有该常量，
但没有找到指向这些常量的代码引用，也没有找到它们含 AC SMM 配置 GUID。

ASUSVGASMI 是一个需要特别纠正的 GUID 误报：公开 EC GUID 虽存在于 RVA `0x1FB0`，
但没有代码或静态指针引用它。其 `0x1EE0` 实际是另一个 GUID
`2A82FCE6-8BB6-413E-B9EB-45DFC0522DF3`，因此由该接口形成的共享上下文
`+0x5A` 和槽 0 调用**不计入 EC 消费者**。ASUSVGASMI 已确认的 EC 使用是上述
AC SMM 配置表 `+0x100` 路径。

本表覆盖全固件中两个 EC GUID 的字节引用及可追踪的获取/调用链。若某模块不引用
GUID、只从其他模块间接接收指针，本轮扫描不能保证发现；方法语义名称也未恢复。

## 结论边界

本次定位针对 AcpiModeEnable 对公开 EC 表的使用方式。AC SMM 表的实际装载地址及其
在 SVAM 后的行为没有动态采样，不能将其列为已证故障。本文未制作或验证永久固件修复。
