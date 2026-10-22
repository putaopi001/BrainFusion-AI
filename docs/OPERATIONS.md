# BrainFusion-AI RC 操作手册

仅针对隔离候选 `BF-RC-20261021.1`。正式容器当前运行于 18100/18180；下列命令不得替换 `docker-compose.rc.yml` 为正式 Compose。RC 启动会对其挂载的 RC SQLite 建表/补列，因此启动前确认 Compose 和数据库路径仍指向 `E:\BrainFusion-Runtime\release-candidate\brainfusion-rc-20261021`。

## 路径与服务

| 项目 | 路径或地址 | 用途 |
|---|---|---|
| 主源码 | `E:\BrainFusion-AI` | 唯一发布候选源码目录 |
| Codex worktree | `C:\Users\mechrevo\.codex\worktrees\1924\BrainFusion-AI` | 独立旧 worktree；有独有修改，未删除 |
| RC Compose | `E:\BrainFusion-AI\docker-compose.rc.yml` | RC 独立容器配置 |
| RC runtime/SQLite | `E:\BrainFusion-Runtime\release-candidate\brainfusion-rc-20261021\runtime` | RC 病例、数据库和分析工件 |
| RC 私有配置 | `E:\BrainFusion-Runtime\release-candidate\brainfusion-rc-20261021\config` | 独立 PACS / 本地账户配置；不入 Git |
| 模型只读挂载 | `E:\BrainFusion-Runtime\results\nightly\2026-10-10\20261010T000643_ec1cf8da\relocated-runtime\model` | RC 当前模型输入；与另一相同 hash 模型副本的路径关系见空间清单 |
| 正式 runtime | `E:\BrainFusion-Runtime\results\nightly\2026-10-20\20261020T1815_real_nifti_compose_demo_fixed\runtime` | 旧正式容器挂载；本轮未改 |
| 本机数据根 | `E:\BrainFusion-Data` | 公开数据集、PACS 候选和派生文件；不是 RC writable runtime |
| Conda 环境 | `E:\BrainFusion-AI\.conda\brainfusion`；另有 `E:\.conda\envs\brainfusion` | 两个路径均保留；用途不可简单互换 |
| RC Web / API | `http://127.0.0.1:18184` / `http://127.0.0.1:18104` | 浏览器和后端 |
| 正式 Web / API | `http://127.0.0.1:18180` / `http://127.0.0.1:18100` | 已按独立审批包部署冻结 tag；本次几何修复验收未触碰 |
| 隔离 Orthanc | `http://127.0.0.1:18142` | Stage7 独立卷；保留合成验收 Study 与获准隔离阅片的 UPENN-GBM-00001 |

## 启动、停止与健康检查

在 PowerShell 执行：

```powershell
Set-Location E:\BrainFusion-AI
docker compose -f .\docker-compose.rc.yml ps
docker compose -f .\docker-compose.rc.yml up -d
docker compose -f .\docker-compose.rc.yml ps
Invoke-RestMethod http://127.0.0.1:18104/
Invoke-WebRequest http://127.0.0.1:18184/ -UseBasicParsing | Select-Object StatusCode
```

停止 RC（容器和数据保留）：

```powershell
docker compose -f E:\BrainFusion-AI\docker-compose.rc.yml stop
```

查看有限日志：

```powershell
docker compose -f E:\BrainFusion-AI\docker-compose.rc.yml logs --tail 100 backend
docker compose -f E:\BrainFusion-AI\docker-compose.rc.yml logs --tail 100 frontend
```

日志可能包含病例标识或本机路径，不要直接上传到公开工单。健康检查与容器身份：

```powershell
docker inspect brainfusion-rc-20261021-backend --format '{{.State.Status}} {{.State.Health.Status}} {{.Image}}'
docker inspect brainfusion-rc-20261021-frontend --format '{{.State.Status}} {{.State.Health.Status}} {{.Image}}'
docker inspect brainfusion-rc-20261021-backend --format '{{json .Mounts}}'
```

已构建镜像 ID：backend `sha256:b14a640a2a5811ac5a980da8349a7a2d0d972150b342035f99a503c061459ce2`；frontend `sha256:4c6f389300d1900f32d1d7ec5eeba6cd721acdebf0370537f3ad358e560d4bfb`。配置摘要在 [`RELEASE_CANDIDATE_20261021.md`](RELEASE_CANDIDATE_20261021.md)。

## 检查数据库和模型挂载

RC API 数据库在容器内 `/app/runtime/brainfusion.db`，宿主机为上表 RC runtime 下的 `brainfusion.db`。正式 runtime 是另一路径；查看正式容器挂载只用于核对，不要启动或写数据库。

模型目录在容器 `/models` 且为只读；权重为 `models/model.pt`。本轮检查其大小为 18,840,620 bytes，SHA-256 为 `860ccb3f1c21c99d0410ad8a1ac4ef6b8fab60cec0a503b0ba42675741a750ae`。在 PowerShell核对：

```powershell
Get-FileHash 'E:\BrainFusion-Runtime\results\nightly\2026-10-10\20261010T000643_ec1cf8da\relocated-runtime\model\models\model.pt' -Algorithm SHA256
```

## PACS 安全门控

```powershell
$s = Invoke-RestMethod http://127.0.0.1:18104/pacs/status
$s | ConvertTo-Json -Depth 6
```

RC/正式 BrainFusion PACS 门控按原配置保持关闭；不得通过改 JSON、环境变量或指向正式服务来打开。独立 Stage7 Orthanc 有独立认证和数据卷，归档中保留合成验收 Study 与 UPENN-GBM-00001；四序列 QIDO/WADO 与隔离 Cornerstone 显示已实测。凭据只在本机秘密管理位置处理，不写入仓库、命令历史或本手册。不要清空该卷或重复导入数据。

## RC 备份与恢复

本轮备份根：`E:\BrainFusion-Runtime\backups\closeout-20261021T194500`。其中包括 E/C 工作区恢复快照、RC SQLite 在线备份、上传/配置副本、RC Compose/版本说明和 SHA-256 清单。SQLite 备份完整性检查为 `ok`。

对后续备份，先在 RC 运行时使用 SQLite backup API 生成一致性副本；不要直接复制活动 `.db` 并删除 `-wal` / `-shm`：

```powershell
$src = 'E:/BrainFusion-Runtime/release-candidate/brainfusion-rc-20261021/runtime/brainfusion.db'
$dst = 'E:/BrainFusion-Runtime/backups/brainfusion-rc-backup.db'
@'
import sqlite3, sys
s = sqlite3.connect('file:' + sys.argv[1] + '?mode=ro', uri=True, timeout=30)
d = sqlite3.connect(sys.argv[2], timeout=30)
s.backup(d); d.close(); s.close()
'@ | & 'E:\.conda\envs\brainfusion\python.exe' - $src $dst
```

检查副本：

```powershell
& 'E:\.conda\envs\brainfusion\python.exe' -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute('pragma integrity_check').fetchone()[0]); c.close()" 'E:\BrainFusion-Runtime\backups\brainfusion-rc-backup.db'
```

恢复仅限 **RC/本次修复测试 runtime**：先停止相应隔离 Compose，确认恢复文件和目标仍为隔离路径，再恢复数据库并检查健康、病例和报告。不要照此对正式 runtime 执行恢复；正式库恢复或迁移必须新的明确审批。正式部署验收记录在 `E:\BrainFusion-Runtime\backups\production-preflight-20261021T205339\production-deployment-acceptance.json`；备份原件不覆盖。源码恢复补丁可在对应 Git HEAD 上应用，恢复快照的 `tracked-changes.patch` 已做只读反向可应用检查；未跟踪文件按 manifest 哈希核对。

## 常见问题

- **18104/18184 被占用**：确认占用者和容器名，不要停止正式或 Orthanc 容器来腾端口。RC 只能在隔离端口运行。
- **backend unhealthy**：查看 `logs --tail 100 backend`；核对 RC runtime/config 存在、Compose 的数据库仍为 `/app/runtime/brainfusion.db`、模型挂载只读且权重文件存在。不要把正式 runtime 路径改入 RC。
- **前端页面 200 但 API 失败**：确认 backend healthy、`CORS_ORIGINS` 与 `18184` 一致。
- **没有当前分析报告**：检查病例历史与分析状态；不要用随机/模拟输出填补，也不要为了演示直接重复推理。
- **PACS 连接失败或 401**：RC 当前 fail-closed 是预期状态；认证由本机维护者核对，不要在 Git 或对话中贴凭据。
- **本机 pytest 环境**：本轮使用 `E:\BrainFusion-AI\.conda\brainfusion` 和 E 盘 basetemp；定向核心回归结果见 `E:\BrainFusion-Runtime\results\dicom-pacs-acceptance-20261021\evidence\core-pytest-20261022.xml`。如果依赖缺失，停止并报告，不要安装到正式运行时。

