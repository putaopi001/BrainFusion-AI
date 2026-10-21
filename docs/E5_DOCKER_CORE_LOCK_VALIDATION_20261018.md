# E5 核心依赖锁验证（2026-10-18）

本次为 Docker 配方的可复现性补强，不代表 Docker/Linux 验收通过。

## 修改

- 将 Docker 专用 `backend/requirements-core.txt` 中 Pillow 从 `12.3.0` 调整为 `12.2.0`。Docker 后端基础镜像是 CPython 3.10；目标平台解析确认，Pillow 12.3.0 没有可用的 CPython 3.10 Linux wheel，12.2.0 有 manylinux wheel。本机主环境锁和历史扩展清单未改。
- 新增 `backend/requirements-docker-core-py310-linux-amd64.txt`，为 CPython 3.10、Linux x86_64、glibc 2.17+ 固定直接及传递依赖的 28 个 wheel SHA-256。
- 新增 `backend/tools/lock_docker_requirements.py`，在不安装包的前提下用 pip 的目标平台解析和二进制 wheel 下载生成哈希锁及 wheel 清单。
- Dockerfile 核心安装改用 `--only-binary=:all:` 与 `--require-hashes`。回归测试确认 Dockerfile 使用该锁、每行含 SHA-256、包名不重复、`requirements-core.txt` 所有直接依赖版本均包含在锁内。

## 验证

- 工具解析结果：28 wheels，共 128,763,593 bytes；wheel 及解析清单位于 `E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T_docker_core_lock_retry/`。
- 核心锁 SHA-256：`abf7b140e9edf590509865b2e39f2f435984d7c77ce17383c060c4f393b1a70b`。
- `tests/test_frontend_delivery.py`：9 passed。
- 全量后端回归：692 passed，0 failed，4 条既有依赖弃用警告；命令从 backend 目录运行项目主解释器，并显式使用 `E:/bfcore18` 短 pytest 临时目录。运行输出在本轮 Codex 执行记录中，pytest 最终摘要为 `692 passed, 4 warnings in 196.48s`。
- 全部写入与测试通过 `backend/tools/run_development_step.ps1` 的独占锁执行；没有安装/升级本机包、改变业务数据库、导入影像或切换服务。

## Compose完整配置补充（2026-10-18）

Compose原来分别安装未封闭传递依赖的CPU Torch/MONAI与scikit-learn/joblib。现新增`backend/requirements-docker-extras.txt`固定顶层版本，并生成`backend/requirements-docker-full-py310-linux-amd64.txt`，合并核心与全部可选依赖为44个带SHA-256的目标wheel。

官方PyTorch CPU索引为Python 3.10提供`torch 2.11.0+cpu`的`manylinux_2_28_x86_64` wheel；Debian Bookworm支持该glibc基线。完整锁同时接受manylinux 2.17 wheel供核心科学计算依赖使用。完整锁平台为Linux amd64；Compose现明确选择`INSTALL_PROFILE=full`并将前后端服务均固定为`platform: linux/amd64`，与哈希锁目标一致。Dockerfile只接受`core`或`full`，两个分支都使用哈希锁及二进制wheel。完整配置从官方PyTorch CPU索引和PyPI解析。

完整锁解析结果：44 wheels，共340,818,465 bytes；锁SHA-256：`74a144eabe00bf96c0e49ab024fa18950673d1d0e95dc66feb91a6eafb768ac2`；44/44 wheel文件的版本与SHA-256均已和锁逐项复核；源wheel与清单见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T_docker_full_lock_retry2/`。未在本机安装这些依赖。`tests/test_frontend_delivery.py`当前11 passed，覆盖两种profile、完整锁、Compose选择与wheel元数据解析。

Compose已将前后端固定到`linux/amd64`，以匹配依赖锁目标；新增架构断言后的定向测试为11 passed。工作树及最终候选全量后端回归均为694 passed、0 failed、4条既有弃用警告。最终源码候选目录：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T2205_pixel_qna_final7/candidate/`；准确文件数、包SHA-256和回归结果以同run目录的`candidate-regression.json`为准。没有安装依赖或启动Docker；此为Windows源码/隔离测试证据。

## 边界与下一步

Python哈希锁现覆盖Dockerfile的core与Compose默认full配置；Dockerfile没有额外的apt/apk安装层，操作系统内容由摘要固定的基础镜像承载。静态锁定不证明wheel能在Linux容器中成功安装。实际镜像拉取/构建/运行、服务健康、持久卷、PACS与Linux特征工作器仍待Docker/WSL环境和专门验收。Docker CLI/WSL尚不可用，故E5继续未验收；本机原生工作流不受影响。
