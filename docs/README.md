# 文档导航

## 使用与开发

- [项目介绍、构建和使用](../README.md)
- [开发与测试](development.md)
- [只读 EFI 运行时采集器](runtime-inventory.md)
- [Linux 诊断环境](../research/linux/README.md)

## 调查结论与证据

- [根因证据与结论边界](root-cause-evidence.md)
- [启动对照与验证范围](investigation.md)
- [EFI 阶段对照结果](efi-stage-results.md)
- [BIOS 306 与 315 对比](bios-306-vs-315.md)
- [固件静态分析](firmware-static-analysis.md)
- [ECProtocol 与 SVAM](ec-protocol-svam.md)
- [EC +0x38 单槽位实验](ec-slot38-experiment.md)
- [DXE/SMM 消费者分析](ec-smm-consumer-analysis.md)
- [EFI/SMM 一手资料](efi-smm-primary-sources.md)
- [UEFI 版本与 Windows 8](uefi-versions-windows8.md)

建议先读根因证据，再按需查看实验记录和静态分析。项目止于原因定位与启动绕过。
原始固件和机器日志仅保留在本地 `local/` 中，不随源码分发。
