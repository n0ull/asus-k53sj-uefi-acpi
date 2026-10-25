# Linux 诊断与固件分析材料

本目录保留用于定位 K53SJ 启动冻结的内核探针、构建配置、采集环境和只读分析工具。
原因定位已完成，结论见 [根因证据](../../docs/root-cause-evidence.md)。
主项目的 `make build` 只构建 AcpiFirst，不下载或编译内核。

## 复现实验

| 实验 | 构建入口 | 说明与结果 |
| --- | --- | --- |
| EFI 阶段探针 | `bash research/linux/build-stage-probe.sh` | [构建依赖和菜单](STAGE3.md)、[实机结果](../../docs/efi-stage-results.md) |
| 运行时清单 | `bash scripts/build-runtime-inventory.sh`，先构建 stage3 | [采集与匹配](../../docs/runtime-inventory.md) |
| EC WATCH | `bash research/linux/build-ec-watch.sh` | [只读观察方法表转换](../../docs/ec-protocol-svam.md) |
| 单槽位对照 | `bash research/linux/build-ec-slot-experiment.sh` | [显式启用的临时 RAM 干预及清理](../../docs/ec-slot38-experiment.md) |

所有命令从仓库根目录执行，输出位于 `build/research/` 的对应子目录。
内核基于 Linux 7.2.7，源码摘要保存在 `kernel-source.sha256`。
`K53_KERNEL_CACHE` 控制 Linux 源码/编译缓存，`JOBS` 控制并行编译数。
探针逐层应用：stage3 → EC WATCH → slot38；缓存已包含后一级探针时，
构建前一级会拒绝混用，需改用新的缓存目录。

对应 OVMF 检查按需运行，要求先构建相应实验镜像：

```sh
python3 research/linux/test-stage-probe.py
python3 tests/test_runtime_inventory.py
python3 tests/test_ec_watch.py
python3 tests/test_ec_watch.py --slot38
```

这些检查不在默认 `make test` 中。OVMF 不含本机 EC 固件，不能验证本次故障机制；
EC 检查验证无匹配时拒绝操作的分支，实机因果证据另见上述实验记录。

## 静态分析工具

- `inspect-runtime-pe.py`：索引 UEFIExtract 的 PE 文件与 GUID 字节引用。
- `match-runtime-inventory.py`：按入口 RVA 和屏蔽重定位后的签名匹配运行时映像。
- `compare-firmware.py`：按 FFS GUID、解压 PE 与节摘要比较两个固件提取目录。

这些工具只读取本地输入并向标准输出写 JSON，不执行固件。参数见各脚本文件头，
结果解释见 [固件静态分析](../../docs/firmware-static-analysis.md) 和
[306/315 对比](../../docs/bios-306-vs-315.md)。GUID 命中不等于提供该协议或已执行。

## 基础材料与许可

- `patches/linux-7.2.7-k53sj-diag2.patch`：基础调用日志、原始端口 I/O 日志和提前启用参数。
- `apply_phase_probe.py`、`apply_ec_watch.py`、`apply_ec_slot_experiment.py`：分层应用后续探针。
- `ec_slot_guard.h`：内核探针和主机测试共用的写入/清理守卫。
- `configs/diagnostic.config`：诊断构建配置；`arch-original.config`：配置来源，供比较。
- `initramfs/init`：最小采集环境；`stage-probe-grub.cfg`：阶段实验菜单。

Linux 补丁遵守上游原有许可，不能以仓库根目录 MIT 许可替代。
仓库不包含 Linux 源码、BusyBox 二进制、原始固件或生成的内核/ISO。
