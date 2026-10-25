# K53SJ BIOS 315：静态路径与 SVAM 实现

日期：2026-10-25。本文记录模块、调用路径及 SVAM 实现。动态结果见 [ECProtocol 与 SVAM](ec-protocol-svam.md)，最终因果定位见 [根因证据](root-cause-evidence.md)。

## 输入与工具

- 用户提供的 `K53SJAS.315`，2,621,440 字节。
- 输入 SHA256：`126ee0fa737e35071a4f383b7e1be1579f1e069755bdc6379d96ee3f3b90f8f8`。
- 使用 [UEFITool 官方项目](https://github.com/LongSoft/UEFITool) 发布的 UEFIExtract A76。
  Linux 工具包的 SHA256 与该官方发布 API 给出的 digest 核对通过。
- 提取、PE 头检查及反汇编均只针对本地副本；原始 BIOS 没有修改，没有执行固件模块。
- 原始模块、反汇编和报告保存在 Git 忽略的 `local/firmware-analysis/`；仓库不分发固件二进制。

## 已定位模块

模块名来自固件 UI section，GUID 来自该固件的 FFS 元数据。

| 模块 | FFS GUID | 提取出的 PE 大小 |
| --- | --- | ---: |
| AcpiModeEnable | `750890A6-7ACF-4F4F-81BD-B400C2BEA95A` | 4,768 |
| Runtime | `CBC59C4A-383A-41EB-A8EE-4498AEA567E4` | 51,552 |
| PchSmiDispatcher | `B0D6ED53-B844-43F5-BD2F-61095264E77E` | 21,696 |
| SmmDispatcher | `4A37320B-3FB3-4365-9730-9E89C600395D` | 14,336 |
| SmmBase | `D0632C90-AFD7-4492-B186-257C63143C61` | 10,592 |

这些 PE 均为 x86-64，首轮解析未发现“此路径其实只有 32 位代码”的证据。
PE 的首选 ImageBase 不是实机装载地址；下述地址均用 RVA，不能直接写成运行时物理地址。

## AcpiModeEnable 中的对应路径

该 PE 的入口 RVA 为 `0x870`。静态控制流中可以看到：

1. 通过 SMM 相关接口区分路径，并取得后续协议指针。
2. RVA `0x7C4` 附近，以 `0xA0` 和 `0xA1` 作为两个上下文值，分别提交
   RVA `0x474` 和 `0x57C` 的回调。这与实际 FADT 的 ACPI_ENABLE/ACPI_DISABLE 值配对一致。
3. RVA `0x474` 的路径处理 PM/GPE 寄存器和 CMOS 状态，并在一个条件性协议回调之后，
   读取 `0x404`、设置最低位，再写回。与 PM1a_CNT 中 SCI_EN 的位置吻合。
4. 设置 SCI_EN 后还会遍历一条动态链表，通过节点内的函数指针调用回调；结尾写 POST 端口。
5. RVA `0x57C` 的配对路径恢复相关状态，并清除 `0x404` 的最低位。

这说明 ACPI 启用请求在固件侧不是一条孤立的置位操作。一次 OS 端口写入还可能经过
分发器、条件性协议调用和回调链，因此仅凭 OS 冻结边界不能断言具体哪段固件内部代码卡死。

### EC 共享协议的识别

AcpiModeEnable 取得 GUID `34CF7EC3-50F4-4544-8F50-FB1F9FF60748` 的协议后保存指针，
在启用路径中有表内偏移 `0x38` 的条件性调用，在禁用路径中有偏移 `0x40` 的调用。
后续运行时清单已将公开实例对应到 ECProtocol。仅搜索 GUID 字节会产生误报，
完整生产者/消费者调用链及 ASUSVGASMI 的误报修正见 [消费者审查](ec-smm-consumer-analysis.md)。
37 个方法的正式语义名称尚未恢复。

## 阶段实验的作用

静态分析不能独立确定故障发生在 SVAM、后续运行时处理还是变量服务调用之后。
同镜像对照已确认 PRE_SVAM 成功、POST_SVAM 失败，因而将动态调查收窄到
SVAM 及其状态变化，见 [阶段结果](efi-stage-results.md)。

## Runtime 服务入口的静态对应

进一步追踪原始 Runtime PE 的初始化代码，而非仅按模块名称判断。
RVA `0x638` 从传入的 x64 System Table `+0x58` 取得 RuntimeServices，保存于
模块全局 RVA `0xB260`；`+0x60` 的 BootServices 保存于 `0xB268`。
因此后续对该 RuntimeServices 指针的写入可按标准表布局解释：

| 服务 | 表内偏移 | 被写入的函数 RVA | 写入指令 RVA |
| --- | --- | --- | --- |
| SetVirtualAddressMap | 0x38 | 0x199C | 0x1BC5 |
| ConvertPointer | 0x40 | 0x1808 | 0x1BD7 |
| SetVariable（一个初始化路径） | 0x58 | 0x5730 | 0x5AD9 |
| SetVariable（另一初始化路径） | 0x58 | 0x5CC0 | 0x5EFD |

两个变量服务入口都调用 RVA `0x5228`，外围状态处理不同。后续运行时清单将当次
SetVariable 对应到 RVA `0x5730`，但不能据此认定变量服务是冻结原因；POST_SVAM
探针在 DUMMY 调用之前已复现故障。所有地址仍为该 PE 内 RVA。

## SVAM 实际控制流

在 PRE_SVAM 成功、POST_SVAM 失败的真机对照之后，逐段检查 Runtime RVA 0x199C。
以下为本机二进制观察，不是用现代 EDK2 代码替代 AMI 实现：

| 区间 RVA | 静态行为 |
| --- | --- |
| 0x19A7–0x19D7 | 检查是否已有映射，写入本次映射指针；向端口 0x80 输出 0xB0 |
| 0x19DE–0x1A18 | 遍历以 0xA940 为表头的链表，从节点取得回调、上下文及事件参数并调用 |
| 0x1A1A–0x1A6F | 遍历以 0xA930 为表头的映像列表，转换映像基址并调用 0x1498；自身映像延后 |
| 0x1A71–0x1A8F | 对运行时服务表各指针槽调用 0x1808 |
| 0x1A91–0x1AF0 | 转换配置表指针及系统表中的相关字段 |
| 0x1AF5–0x1B52 | 重新计算运行时服务表和系统表 CRC |
| 0x1B55–0x1B7F | 处理之前延后的自身映像重定位，向端口 0x80 输出 0xB1，然后返回成功 |

0x1808 在映射描述符中查找地址，再将目标指针加上 VirtualStart−PhysicalStart。
0x1498 解析 PE 重定位目录；对 DIR64 项按差值更新，存在原始 fix-up 数据比较逻辑。
后续 EC WATCH 确认公开 EC 表内方法地址发生转换；这不证明重定位计算本身错误，
故障机制在于消费者跨执行域使用转换后的地址。

两个链表相差 0x10，节点中字段相对 Link 的偏移与 Runtime Architectural Protocol
的 EventHead/ImageHead 布局相符，可作为结构识别的交叉验证。
[EDK2 的协议定义](https://github.com/tianocore/edk2/blob/master/MdePkg/Include/Protocol/Runtime.h)
只用于字段布局参考，不证明本机使用当前 EDK2 实现。

新增只读脚本 `research/linux/inspect-runtime-pe.py` 可以对 UEFIExtract 的 PE body.bin
建立 GUID 字节引用索引，包括 Runtime Architectural Protocol 与公开 EC 协议。
结果仅保存于本地忽略目录；存在 GUID 不等于提供该协议，更不等于该模块的回调已执行。

后续 [运行时清单采集](runtime-inventory.md) 已取得装载映像基址、事件回调和公开 EC
协议地址，并通过 RVA 与入口签名对应模块；该清单不能替代 SMM 内部指令级跟踪。
