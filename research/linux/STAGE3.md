# 第三轮：EFI 运行时与 ACPI 启用的分段研究

目的：定位触发条件，不安装系统、不制作长期引导入口、不刷 BIOS。

## 探针设计依据

精确 Linux 7.2.7 在 `efi=debug` 时会直接跳过 `efi_unmap_boot_services()` 的主体。
此外，EFI 虚拟转换末尾的 `efi_delete_dummy_variable()` 会调用 SetVariable 删除特定
GUID 的 DUMMY 变量，它不是只读操作。`efi_no_storage_paranoia` 不能单独跳过这次调用。
因此需要将 SVAM、权限更新和第一次变量服务调用拆开。

主源及限制见 [EFI/SMM 研究](../../docs/efi-smm-primary-sources.md)。

## 构建与虚拟机验证

Ubuntu/WSL x86-64，除主项目构建依赖外需要 flex、bison、bc、libssl-dev、libelf-dev、
curl、xz-utils、busybox-static、cpio、patch。源码默认缓存到 Linux 用户缓存目录，
避免在 Windows 文件系统中编译大量内核文件。可以设置 `K53_KERNEL_CACHE` 和 `JOBS`。

```sh
bash research/linux/build-stage-probe.sh
python3 research/linux/test-stage-probe.py
```

源码版本和摘要沿用已校验的 Linux 7.2.7；先应用第二版累计补丁，再加入当前的阶段探针。
源码已打补丁但补丁内容改变时，脚本会拒绝重复应用，需指定新的缓存目录。
输出为 `build/research/stage3/K53SJ-EFI-STAGE3.iso`，不进入 Git。

## 菜单

| 项 | 改变的内容 |
| --- | --- |
| 1 | 仅跳过 EFI 初始化末尾的 DUMMY 删除；ACPI 仍在原时机启用 |
| 2 | SVAM 成功返回后、后续 helper 之前，单次请求启用 ACPI |
| 3 | 实际 SVAM 调用之前，单次请求启用 ACPI，作为前置对照 |
| 4 | 运行时入口/权限处理完成后、DUMMY 前，单次请求启用 ACPI |
| 5 | DUMMY 返回之后，单次请求启用 ACPI |
| 6 | 原顺序基线，不跳过、不提前启用，保留真实 I/O 指令前后标记 |

每次启动只选择一项；不要合并多个阶段参数。成功设置 SCI_EN 后，后面的 ACPI 启用
会走已启用分支，不能用一次启动连续测试四个位置。每项应从完全关机后独立启动，
并记录 BEFORE SCI_EN；如果原本已经为 1，需要在解释结果时指出。

所有菜单统一使用 `efi=debug` 和 `log_buf_len=8M`；不依赖大量 initcall 跟踪来定位。
阶段性 ACPI 探针仅在 DMI 产品名为 K53SJ 且 ACPI 已启用支持时执行。

## 已有实机结果

BASELINE、skip-DUMMY 和 POST_SVAM 均报告冻结，PRE_SVAM 成功。
原始标记、日志摘录和证据限制见 [EFI 阶段对照结果](../../docs/efi-stage-results.md)。

## 解释边界

- skip DUMMY 成功、基线失败：定位到该变量服务调用造成的状态变化；不等于证明变量 GC 是根因。
- post SVAM 立即失败、pre SVAM 成功：优先查转换事件/重定位与 SMM 使用对象之间的关系。
- post SVAM 成功、pre DUMMY 失败：优先拆分后续入口或权限更新区间。
- pre DUMMY 成功、post DUMMY 失败：更直接支持变量服务调用的影响。
- 真正 outb RETURN 已出现时，不能再称为 outb 没有返回；必须继续看之后的 SCI_EN 读取或其他状态。

OVMF 原本已在 ACPI 模式，虚拟机只能验证菜单、探针位置、跳过分支和 shell，
不能模拟本机的真实 ACPI SMI 失效。没有增加新的变量写入；基线仍会执行 Linux 原有的 DUMMY 调用。
