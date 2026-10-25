# EFI 运行时清单采集器

采集结果已用于识别 ECProtocol；结果见 [方法表与 SVAM](ec-protocol-svam.md)。本文说明工具的构建、使用与限制。

## 为什么需要它

同一阶段诊断内核中，SCI_EN=0 时在 SVAM 前执行 ACPI_ENABLE 成功，在 SVAM 后立即
执行则冻结。静态分析已确定 Runtime 的通知链、重定位链及转换函数，但不知道实际
加载了哪些运行时映像、通知回调属于哪个模块、ACPI 共享方法指针指向哪里。

新程序 RuntimeInventory.efi 在 ExitBootServices 之前只读取这些信息，不调用
SetVirtualAddressMap、SetVariable、ACPI_ENABLE 或 ACPI_DISABLE，也不执行未知协议方法。
它会调用标准文件系统服务，把一份报告写到用户标记的卷。普通固件的标准启动行为不在
此应用的控制范围内；不能把整个启动过程称为绝无 NVRAM 活动。

## 文件

先按 [阶段探针说明](../research/linux/STAGE3.md) 构建 stage3 内核和初始文件系统，
再运行 `bash scripts/build-runtime-inventory.sh`。
输出位于 `build/research/runtime-inventory/`：

- K53SJ-RUNTIME-INVENTORY.iso：GRUB 直接入口，不需要 EFI Shell。
- K53PROBE.TAG：日志卷选择标记，需复制到一个固件可读写的 FAT32 U 盘根目录。
- RuntimeInventory.efi、SHA256SUMS。

标记文件不包含在 ISO 文件系统中，避免将只读 ISO 自身选作日志卷。
已有文件不覆盖，依次选用 K53SVAM-00.TXT 至 K53SVAM-99.TXT。

## 真机步骤

1. 将 ISO 放入 Ventoy 数据分区。将 K53PROBE.TAG 放入另一个 FAT32 U 盘根目录，
   可以使用现有 Windows 安装 U 盘，无需重新格式化。只保留一个带此标记的卷。
2. 完全关机后从 Ventoy UEFI 启动此 ISO，选择第 1 项 SAVE firmware inventory。
3. 确认出现 `Inventory save ... Success`，拍照保存状态。报告已 Flush/Close。
   EFI 应用返回后 GRUB 可能显示 `Failed to boot both default and fallback entries`，
   这是没有交给操作系统、而是返回了 GRUB，不表示之前的报告保存失败。
4. 按键返回菜单后，选择第 2 项 POST_SVAM。观察是否仍停在 outb 之前，拍最后画面。
   这一步检查新增采集过程是否改变了故障条件；如果不能返回菜单，不要求操作 GRUB
   命令行，保留报告及画面。
5. 完全关机后，将标记卷上的 K53SVAM-xx.TXT 复制到本地证据目录。

若显示 RuntimeArch 不存在、列表 INVALID/incomplete 或无法保存，拍下信息并保留报告，
不要据此判断某模块缺陷；本机协议布局仍需报告交叉核验。

## 采集与解析边界

- 读取范围由 EFI 内存图校验；保留/MMIO/不可用区域不读取，链表最多 128 项。
- 报告包含 runtime image 的基址、大小、入口 RVA/64 字节签名、事件回调及所属映像 RVA，
  以及 ACPI 共享协议头 9 个指针大小的字段（未知字段不当作可调用方法）。
- 清单反映加载此采集器时的状态；Linux 启动前可能还有后续注册。相同启动会话中运行
  POST_SVAM 对照有助于核查干扰，但不等于在 SVAM 内部采样。
- 无匹配的回调地址不等于非法地址，它可能属于不在 runtime image 链上的模块或固件代码。
- Linux 仍冻结时，不能用“最后列出的回调”推断卡死回调；所有 SVAM 回调可能都已返回，
  状态破坏可能在后续 ACPI SMI 才暴露。

解析命令（输出放入忽略目录）：

```sh
python3 research/linux/match-runtime-inventory.py local/evidence/K53SVAM-00.TXT \
    local/firmware-analysis/K53SJAS.315.dump > local/firmware-analysis/runtime-matches.json
```

匹配使用入口 RVA 与 64 字节签名，屏蔽 DIR64 重定位项。唯一签名匹配仍不是整个映像的
完整性认证；多个候选保留为 ambiguous，不猜测所有者。

## 已完成的本地验证

`python3 tests/test_runtime_inventory.py`：OVMF 实际解析 image/event 链；单标记保存；
已有报告保持原样；无标记及双标记拒绝报告写入；分发 ISO 的 GRUB 入口保存成功。
`python3 tests/test_runtime_matching.py`：合成 PE 的重定位字节变化可匹配，代码变化和
不足长度的签名被拒绝。OVMF 测试不代表已验证 K53SJ 的私有协议布局或 SMM 故障。
