# Linux adaptation policy / Linux 适配维护规范

[简体中文](#简体中文) · [English](#english)

## 简体中文

### 目标与版本

持续维护与上游对应版本行为一致的 Linux 桌面程序和 CLI。从 3.0.3 起跟随上游版本，不追补更早版本。Linux 应用版本跟随对应上游版本，同一版本的 Linux 打包修订使用包修订号区分。

每次同步先获取并固定上游最新提交，再将 Linux 移植提交 rebase 到其后，保持“上游历史 → Linux 移植”的线性顺序，不通过 merge 提交同步上游。已推送的适配分支重排后使用带明确旧提交校验的 `--force-with-lease` 更新；不移动已有 Release 标签。每次同步上游时，检查 GUI、CLI、依赖、资源和平台逻辑的变化，只修改实际需要适配的部分。采用功能分支，不擅自合并主分支、发布 Release 或改写已有发布。

本文件规定维护目标和验收流程，不代表任何版本已经构建、安装或通过实机验证。具体状态记入现有 changelog。

### 支持范围与产物

| 项目 | 目标 |
| --- | --- |
| 架构 | x86_64、ARM64 |
| 系统基线 | Ubuntu 22.04+、Debian 12+、Fedora 43+ |
| 包格式 | 每种架构提供 deb、rpm、AppImage，共六种产物 |
| 用户运行环境 | 成品包含应用运行所需内容，不要求用户建立 Python 开发环境；系统依赖需明确记录 |

最低系统要求不能因构建机或依赖升级而无意提高。确需变更时，先讨论并记录；有限测试不构成对所有未来系统版本的兼容性承诺。

完整覆盖 GUI 与 CLI 的连接、FL23、Look 导入和离线转换、槽位恢复、出厂恢复、声音、竖屏、事务记录、恢复流程及随包资源。检查各入口的参数、结果、错误处理和恢复语义，不能仅以 GUI 可启动作为移植完成标准。

Linux 无原生 Lightroom Classic 宿主，其原生宿主集成不在支持范围内；这不排除独立于 Lightroom 的离线转换功能。其他不兼容功能必须先报告并确认处理方式，不得静默删除、跳过或错误显示成功。上游新增功能同样适用。

### 实现与权限

- 复用现有核心业务、相机操作和恢复逻辑；平台差异集中在现有平台层及必要的构建入口，不复制一套 Linux 核心实现。
- 只做完成适配所需的最小完整修改，保持 Windows/macOS 行为，不顺带重构或引入无实际需要的框架。
- 项目内使用 `.venv` 开发、测试和构建，沿用现有依赖管理方式，记录必要的 Linux 构建依赖。
- 沿用现有打包结构，提供可重复执行的 Linux 构建入口，统一读取应用版本，避免多个位置手工维护版本号。
- USB 使用仅针对相机 `054C:0E8A`、`054C:0336` 身份的 udev 规则，首次显式连接时自动配置，必要时由系统弹窗授权，无需用户手工执行命令；配置后以普通用户运行。权限和卸载存储的实现可因平台不同，但操作结果及错误处理应与上游一致。
- 系统级修改需要明确授权；AI 代理遇到 `sudo` 必须报告命令和原因，由用户执行，不得执行或提权。未经明确授权不使用其他代理。

### 相机安全与数据

遵守 [AGENTS.md](AGENTS.md) 的完整相机安全约束。先完成离线验证；只有明确设备操作才打开 USB，启动和离线命令不访问相机，一次只开一个服务会话。

未知写入结果、超时或断开后停止，保留事务证据，不自动重复写入。保持完整读回及原有检查，保护当前校准、未选槽位及标题和无关设置。桌面直接操作与旧 CLI 分别保留各自的备份、恢复合同，不把 CLI 的备份要求强加给桌面直接操作。

升级和卸载不得删除用户设置、事务证据和恢复数据。固件、机身备份、校准、照片、凭据及私人日志不得进入仓库或发行包。

### 每个版本的验证流程

1. 对比上游变化，核对 GUI/CLI 功能及平台差异，报告新增限制。
2. 执行现有离线测试，并为 Linux 新增逻辑补必要回归测试。覆盖路径、子进程、资源、权限、设备忙、超时、断开和恢复处理，确认未知写入结果不会触发自动重写。Windows/macOS 相关回归在对应原生环境检查；无法完成的项目标为未测。
3. 构建六种产物，检查版本、架构、资源、依赖及包内容，防止混入私人文件。
4. 使用 QEMU 验证 x86_64、ARM64 各自的 Ubuntu 22.04、Debian 12、Fedora 43，共六个干净系统环境。Ubuntu/Debian 检查 deb 与 AppImage，Fedora 检查 rpm 与 AppImage。环境不依赖项目源码或预装的 Python 开发环境。
5. 检查安装、桌面入口、GUI/CLI、离线转换、随包资源、升级与卸载。验证适用的 X11/Wayland 行为，以及 AppImage 的可执行权限、FUSE 依赖和解包运行。存在上一版 Linux 包时，验证升级后设置、事务和恢复数据仍可用。另选较新发行版做兼容性抽查。
6. 离线检查通过后，按变更范围与用户安排实机验收。先只读连接，再进行约定的写入和恢复；每轮 I/O 完全结束后才请用户操作相机。冷启动后分别检查菜单名称、预览、照片/回放、元数据、原有 FL/FL2/FL3、声音及竖屏。GUI 和 CLI 的不同合同分别验收。不在真实写入中通过拔线或断电制造故障，中断处理主要使用模拟和已有事务证据验证。
7. 记录版本、架构、系统、包格式、检查内容以及通过、失败、未测项。QEMU、原生主机、真实 USB 和实机功能验证分别标注；不将上一版本的实机结果自动算作当前版本已实测。

构建成功、离线测试、QEMU 验证和完整读回均不能代替真实相机重启及效果验收。缺少某架构的真实 USB 测试时，不能宣称该架构已通过实机验证。

### 仓库边界与维护记录

仓库只保留适配代码、必要回归测试、可复用的构建打包配置及维护文档。QEMU 镜像、虚拟机配置、环境搭建脚本和运行产物留在仓库外，可持续复用，不提交仓库。

本文件作为长期适配规范。用户说明保留在中英文 README，开发细节放入现有 development 文档，版本差异与验证记录放入现有 changelog；中英文同步，不为每个版本新增移植指南或研究笔记。Linux 使用方法在实际实现并验证后补充，不把计划写成已完成的支持。

## English

### Objective and versions

Maintain a Linux desktop app and CLI with behavior matching the corresponding upstream version. Track upstream from 3.0.3 onward without backporting earlier versions. The Linux application version follows upstream; use a package revision to distinguish Linux packaging updates for the same application version.

Fetch and pin the latest upstream commit before each sync, then rebase the Linux adaptation commits onto it. Keep a linear upstream-history → Linux-adaptation order; do not sync upstream through merge commits. Update a rebased published adaptation branch with `--force-with-lease` and an explicit expected old commit; do not move existing Release tags. For each upstream update, review changes to the GUI, CLI, dependencies, resources and platform logic, and adapt only what needs changing. Develop on feature branches; do not merge into main, publish releases or rewrite existing releases without authorization.

This document defines maintenance targets and acceptance procedures, not evidence that a version has been built, installed or physically tested. Record actual status in the existing changelog.

### Platforms and deliverables

| Item | Target |
| --- | --- |
| Architectures | x86_64 and ARM64 |
| System baselines | Ubuntu 22.04+, Debian 12+, Fedora 43+ |
| Packages | deb, rpm and AppImage for each architecture: six artifacts |
| User runtime | Bundle application runtime requirements without requiring a Python development environment; document system dependencies |

Build-host or dependency upgrades must not silently raise minimum system requirements. Discuss and record necessary changes first. Limited testing does not guarantee compatibility with every future system release.

Cover both GUI and CLI connection, FL23, Look import and offline conversion, slot restoration, factory restoration, sound, Vertical Display, transaction evidence, recovery flows and bundled resources. Check arguments, results, error handling and recovery semantics for every entry point; a working GUI launch alone does not establish feature parity.

Linux has no native Lightroom Classic host, so native host integration is excluded. Offline conversion independent of Lightroom remains in scope. Report other incompatible features and agree on their treatment before proceeding; never silently remove or skip them, or report false success. Apply the same rule to new upstream features.

### Implementation and permissions

- Reuse existing business logic, camera operations and recovery engines. Keep platform differences in the existing platform layer and necessary build entry points; do not duplicate the core for Linux.
- Make the smallest complete adaptation, preserve Windows/macOS behavior, and avoid unrelated refactoring or speculative frameworks.
- Use a project-local `.venv` for development, testing and builds. Follow existing dependency management and document necessary Linux build dependencies.
- Extend the existing packaging structure with repeatable Linux build entry points and a shared application version source, avoiding manual version edits in multiple places.
- Restrict USB udev rules to camera identities `054C:0E8A` and `054C:0336`, automatically configuring access on the first explicit connection, with system authorization when required and no manual commands; subsequent camera operations run as the ordinary user. Permission and storage-unmount implementations may differ by platform, but outcomes and error handling must match upstream.
- System-wide changes require explicit authorization. AI agents must report any required `sudo` command and its reason for the user to execute; agents must not execute or escalate it. Do not use additional agents without explicit authorization.

### Camera safety and data

Follow all camera safety constraints in [AGENTS.md](AGENTS.md). Complete offline validation first. Only explicit device actions open USB; startup and offline commands must not access the camera. Allow one service session at a time.

Stop on an unknown write outcome, timeout or disconnect, retain transaction evidence, and never automatically repeat the write. Preserve full readback and existing checks, current calibration, unselected slots and their titles, and unrelated settings. Keep the desktop direct-operation and legacy CLI backup/recovery contracts separate; do not impose CLI backup requirements on desktop direct operations.

Upgrades and uninstallation must preserve user settings, transaction evidence and recovery data. Keep firmware, body backups, calibration, photos, credentials and private logs out of the repository and release packages.

### Validation for every version

1. Review upstream changes, check GUI/CLI coverage and platform differences, and report new limitations.
2. Run existing offline tests and add necessary regression tests for new Linux logic. Cover paths, subprocesses, resources, permissions, busy states, timeouts, disconnects and recovery; verify that unknown write outcomes cannot trigger automatic rewrites. Check relevant Windows/macOS regressions on their native environments and mark unavailable checks as untested.
3. Build all six artifacts and inspect versions, architectures, resources, dependencies and package contents, excluding private files.
4. Use QEMU for six clean environments: Ubuntu 22.04, Debian 12 and Fedora 43 on both x86_64 and ARM64. Test deb and AppImage on Ubuntu/Debian, and rpm and AppImage on Fedora. Environments must not rely on project sources or a preinstalled Python development environment.
5. Check installation, desktop entry points, GUI/CLI operation, offline conversion, bundled resources, upgrades and uninstallation. Check applicable X11/Wayland behavior and AppImage executable permissions, FUSE requirements and extracted execution. When a previous Linux package exists, verify that upgrades preserve usable settings, transactions and recovery data. Sample newer distribution releases for compatibility as well.
6. After offline checks pass, arrange physical acceptance with the user according to the changes. Start with read-only connections, then agreed writes and restoration. Ask for physical camera actions only after all I/O has ended. After a cold boot, separately check menu names, preview, photos/playback, metadata, original FL/FL2/FL3, sound and Vertical Display. Validate the distinct GUI and CLI contracts separately. Do not deliberately disconnect or cut power during real writes; primarily validate interruption handling through simulation and existing transaction evidence.
7. Record version, architecture, system, package format, checks, and passed, failed or untested results. Distinguish QEMU, native-host, real USB and physical camera verification. Never automatically carry forward physical acceptance from a previous version.

Successful builds, offline tests, QEMU checks and full readback do not replace camera boot and physical output acceptance. Without real USB testing on an architecture, do not claim physical validation for it.

### Repository boundaries and maintenance records

Keep only adaptation code, necessary regression tests, reusable build/package configuration and maintenance documentation in the repository. Keep reusable QEMU images, VM configurations, environment setup scripts and execution artifacts outside the repository; do not commit them.

This file is the ongoing adaptation policy. Keep user guidance in the English and Chinese READMEs, implementation details in the existing development documents, and version differences and validation records in the existing changelogs. Keep both languages aligned; do not add per-version porting guides or research notes. Add Linux usage instructions after implementation and verification, and never present planned support as completed work.
