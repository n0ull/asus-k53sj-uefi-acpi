# 真机清单：ECProtocol 方法表与 SVAM

日期：2026-10-25。本文记录动态清单与 EC WATCH 的观察；后续单槽位因果验证已完成，见 [根因证据](root-cause-evidence.md)。

## 运行时清单

用户提交 K53SVAM-00.TXT（8,182 字节），SHA256：
`760ed99ccb10cff369b216f92513b4f703aee346e7d17b061451df38da2530a2`。
本地副本位于忽略目录 `local/evidence/stage3-runtime-inventory-00.txt`。
同一采集启动会话之后的 POST_SVAM 照片仍为 SCI_EN=0、outb ENTER 后无 RETURN；
采集并未消除已知故障。

报告列出 22 个运行时映像、11 个事件。入口签名匹配得到 21 个唯一候选，1 个未匹配；
不是对完整映像内容的校验。关键对应如下（地址仅对本次启动有效）：

| 对象 | 真机值 | 对应 |
| --- | --- | --- |
| Runtime 映像 | 0xAAD81000 | SVAM RVA 0x199C、ConvertPointer RVA 0x1808 |
| SetVariable | 0xAAD86730 | Runtime RVA 0x5730；确认本次选择这条入口路径 |
| ECProtocol 映像 | 0xAAD49000 | PE entry RVA 0x2F8，SizeOfImage 0x27E0 |
| ACPI 共享协议 | 0xAAD4AE70 | ECProtocol RVA 0x1E70 |
| 协议 +0x38 | 0xAAD49E74 | ECProtocol RVA 0xE74 |
| 协议 +0x40 | 0xAAD49ED4 | ECProtocol RVA 0xED4 |

已识别的通知包括 Runtime 的 RVA 0x6434，以及 RVA 0xA90（两个不同上下文），
PchReset RVA 0x910、SmmControl RVA 0x690。其他回调不在采集到的 runtime image
范围内，不能称为无效地址，也不能推测最后哪个事件导致故障。

## 从未知协议推进到具体模块

AcpiModeEnable 静态入口通过 BootServices LocateProtocol 获取 GUID
34CF7EC3-50F4-4544-8F50-FB1F9FF60748，保存于其全局 RVA 0x1158。
其 ACPI 启用路径在 RVA 0x53A 条件性调用该协议的 +0x38，随后才操作 SCI_EN。
本次清单将该 GUID 的公开实例对应到了 ECProtocol；不能仅据公开实例就直接证明
SMRAM 内运行的实例保存了完全相同的指针，后续因果结论仍需保留这一边界。

ECProtocol 的 RVA 0xE74 包含针对端口 0x257/0x258 的操作和轮询；检查过的轮询有
计数上限，所以暂不把它简单归为无界等待。未执行这些方法来进行试探。

## 与 SVAM 重定位的具体联系

ECProtocol 的 PE 重定位表包含 RVA 0x1EA8 和 0x1EB0 的 DIR64 项，正好是该共享
实例的 +0x38 和 +0x40。其他前 9 个方法槽也都具有 DIR64 项。
Runtime 的 SVAM 会在通知之后调用映像重定位函数，并按 VirtualStart−PhysicalStart
更新满足原始 fix-up 检查的指针。

这形成了后续 EC WATCH 的可检验预测：同一物理表中的方法值会变为 OS 虚拟地址。
地址转换本身属于正常运行时机制；故障取决于消费者是否仍以原物理执行环境使用这些值。

## EC WATCH：构建与复现

新内核在 EFI runtime code/data 内按页查找 ECProtocol。要求 PE 架构、入口、映像大小
以及 9 个初始方法地址全部匹配，并且候选唯一；不使用上次启动的绝对地址。
在实际 SVAM 前后只读取表，打印 +0x38/+0x40 及各自预期虚拟地址。
不调用 EC 方法、不恢复指针、不跳过固件事件、不修改任何固件内存。

构建：`bash research/linux/build-ec-watch.sh`。
ISO：`build/research/ec-watch/K53SJ-EC-WATCH.iso`。
保留 stage3 内核配置与版本字符串，新增探针必须有 cmdline 参数 `k53diag_ec_watch`。
同一个本地源码缓存增量加入探针后，不可用于构建未含探针的 pristine stage3；
原 stage3 分发文件保持原样，原构建脚本会检查并拒绝混用。

人工步骤：

1. 完全关机，从 Ventoy UEFI 启动新 ISO，选第 1 项 EC WATCH（SVAM 后启用）。
   拍最后画面，重点是 K53EC POST 的 physical_table、changed、translated、slot38/slot40。
2. 再次完全关机，选第 2 项 control（SVAM 前启用），成功后用原 diag-save 导出日志。
   将日志另存为 ec-watch-control.tar.gz，避免覆盖之前的原始证据。

如果 candidates=0/多个或 mapping failed，只能判为采样失败，不能推断表未改变。
OVMF 不包含本机 ECProtocol；本地虚拟机只能覆盖无匹配保护及探针之后的启动，
不能验证真机匹配分支或 SMM 行为。源码没有实施任何修复或 BIOS patch。

本地验证已通过：编译启用 Wall/Wextra/Werror；实际 ISO 在隔离 OVMF 中输出
`K53EC PRE candidates=0`、保护分支 STOP，随后 POST_SVAM 探针返回并到达诊断 shell。
该测试使用 Linux 原生缓存保存高频串口日志，避免 WSL 挂载目录的并发读取错误；
最终日志复制到 `build/research/ec-watch/vm-tests/serial.log`。
ISO SHA256：`d250a3e2b2531aa9b1851fbb93bdf627b730eda409ef8fa10500d39149d3b1d9`。

## EC WATCH 真机结果：前后指针变化已确认

用户提交第 1 项冻结照片和第 2 项控制日志 k.tar.gz。
控制日志 SHA256：`a1fccb73beba7962f81b3610c3b01e47c6e6491963790702161ce2f3aa230706`，
证据副本为 `local/evidence/ec-watch-control.tar.gz`。

两条路径均找到唯一 ECProtocol 候选（base 0xAAD49000），同一物理表 0xAAD4AE70 在
SVAM 后均报告 `changed=9 translated=9/9`。其中：

| 槽位 | SVAM 前 | SVAM 后 / 预期虚拟值 |
| --- | --- | --- |
| +0x38 | 0xAAD49E74 | 0xFFFFFFFEF6949E74 |
| +0x40 | 0xAAD49ED4 | 0xFFFFFFFEF6949ED4 |

第 1 项在此之后读出 SCI_EN=0，outb 0xB2/0xA0 ENTER 后无 RETURN。
第 2 项 cmdline 为 pre_svam：请求前 SCI_EN=0，outb 返回且 SCI_EN=1；之后 SVAM
仍将 9 个指针转换，DUMMY、M15 和 efivars 注册均继续完成。

EC WATCH 直接确认同一物理表的值发生转换；仅凭这项观察，尚不能判断转换是否导致冻结。
后续 [单槽位对照](ec-slot38-experiment.md) 只改变请求期间的 +0x38，建立了该槽值与请求能否返回的因果联系。
