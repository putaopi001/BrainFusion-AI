# BrainFusion AI 前端

当前Vue3/Vite源码，实际页面/范围见项目README和docs/USER_OPERATION_GUIDE、FIXED_DEMO_GUIDE、RELEASE_SCOPE。不是通用模板或容器验收声明。

本机在E:/BrainFusion-AI/frontend，先设置E盘缓存：

```powershell
. ../backend/tools/use_e_drive.ps1
npm run build
$env:BRAINFUSION_WEB_URL='http://127.0.0.1:5179'
npm run test:e2e
```

当前前端由项目start_local.ps1管理，不另起第二服务。基础浏览器测试仅根页面/四序列前置限制，不冒称真实模型全流程。依赖按package-lock.json和实测构建，node_modules不随源码交付；首次安装/浏览器下载也必须先设置E盘npm/Playwright缓存，本轮不重复安装。

构建大块提示保留。Docker/Compose仍未实测，新.dockerignore不是构建通过证据。源包不含数据/模型/主CUDA/独立CPU环境，不能把只有页面源码称为开箱部署完成。
