# 单槽位因果对照：仅临时恢复 EC +0x38

2026-10-25。本实验与前一轮只读 EC WATCH 不同：包含明确启用的临时 RAM 写入。
它不改 BIOS 文件、BIOS 闪存、NVRAM 或磁盘，不是长期修复或通用内核 quirk。

## 目的与可证伪预测

已观察到 SVAM 后，ECProtocol 物理表内 9 个方法指针都变成对应虚拟地址，后续
ACPI_ENABLE SMI 请求冻结。AcpiModeEnable 的静态路径在设置 SCI_EN 之前会间接
调用协议 +0x38。预测：只把该槽临时还原到原物理方法地址，便能使该请求返回。
若仍在同一请求冻结，应降低“只由这个槽触发”的优先级，不能继续宣称已定位。

## 实现范围

- 必须有 `k53diag_ec_restore38` 参数，默认基线菜单没有此参数。
- 必须为 K53SJ、POST_SVAM 探针位置、且 EC WATCH 找到唯一的精确 EC 表。
- 写前检查初始 9 个地址都等于已知方法 RVA 加装载基址，当前 9 个值均等于预期虚拟值。
- 只对物理表 +0x38 写入一个对齐的 64 位指针，回读并记录 match。
- 随后执行同一个 POST_SVAM ACPI 探针。如果它返回，再验证 9 槽状态，只将 +0x38
  恢复成原预期虚拟地址并回读；其他槽位不修改。
- 若请求冻结，清理代码无法运行，完全关机结束该次临时实验。
- 任一匹配条件不满足则 REFUSED，不做替代写入或扩大修改范围。

写入地址按当前启动自动匹配，不使用上一轮的绝对物理地址。
成功判据必须包含 **APPLY match=1、请求前 SCI_EN=0、IO outb RETURN、SCI_EN=1、
CLEANUP match=1**。仅进入 shell 而没有这些标记不能判定因果对照成立。

## 文件及步骤

构建：`bash research/linux/build-ec-slot-experiment.sh`。
镜像：`build/research/ec-slot38/K53SJ-EC-SLOT38-EXPERIMENT.iso`。

1. 完全关机，启动镜像第 1 项 BASELINE（只读），拍最后画面，确认同一内核仍复现。
2. 再完全关机，启动第 2 项 RAM-ONLY TEST。
   若成功，导出日志另存为 slot38-test.tar.gz；若冻结，拍最后标记。

菜单无自动倒计时，不会默认执行 RAM 写入。不需要标记文件、Windows 安装盘或刷写。
即使成功，也只说明 ACPI 启用这一次受单槽干预影响；其他 SMM 调用、电源管理和
长期运行尚未验证，不能把实验镜像当作日常系统启动工具。

## 本地验证边界

真正用于判断是否允许写入的 `ec_slot_guard.h` 与 native C 测试共享；验证初次写入、
清理状态、其他槽变化、空基址及错误初始表的拒绝条件。
OVMF 不含本机 EC 表，因此只能验证运行时保护分支，不测试真实 SMM 或真机内存写入。
从采样源缓存增量加入此实验后，原只读 EC WATCH 构建脚本会拒绝混用；既有镜像不变。

已通过 native 守卫测试、实际内核编译，以及 `python3 tests/test_ec_watch.py --slot38`：
实验参数已生效，但 OVMF 没有 EC 精确匹配时输出 REFUSED、没有 APPLY ENTER，
随后 POST_SVAM 探针返回并进入 shell。不能将此描述为真机写入或修复已验证。
ISO SHA256：`91c217b659a83cd92f99d3b144f749d45b264149397614e2c1bca800330f4698`。

真机结果已收到且满足全部成功判据：基线冻结，临时恢复 +0x38 后 IO 请求返回、
SCI_EN=1、CLEANUP match=1，后续 EFI/ACPI 初始化继续。见[完整因果证据](root-cause-evidence.md)。
