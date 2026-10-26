<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-logo">BF</div>
        <div class="brand-text">
          <div class="brand-name">BrainFusion AI</div>
          <div class="brand-sub">脑胶质瘤智能诊疗</div>
        </div>
      </div>

      <el-menu
        :default-active="activeMenu"
        router
        class="side-menu"
        background-color="transparent"
        text-color="#94a3b8"
        active-text-color="#38bdf8"
      >
        <el-menu-item index="/"><span class="menu-dot"></span>工作台</el-menu-item>
        <el-menu-item index="/cases"><span class="menu-dot"></span>病例管理</el-menu-item>
        <el-menu-item index="/patients"><span class="menu-dot"></span>患者管理</el-menu-item>
        <el-menu-item index="/dicom-archive"><span class="menu-dot"></span>隔离 DICOM 归档</el-menu-item>
        <el-menu-item index="/research"><span class="menu-dot"></span>IDH 与融合研究</el-menu-item>
      </el-menu>

      <div class="sidebar-footer">
        <div class="footer-line">BrainFusion AI v0.1.0</div>
        <div class="footer-sub">教学原型 · 非临床诊断</div>
      </div>
    </aside>

    <div class="main-area">
      <header class="topbar">
        <div class="topbar-title">{{ pageTitle }}</div>
        <div class="topbar-right">
          <el-tag v-if="caseStore.currentCaseId" type="info" size="small" effect="plain">
            当前病例 #{{ caseStore.currentCaseId }}
          </el-tag>
          <el-tag type="warning" size="small" effect="plain">教学原型 · 非临床诊断</el-tag>
        </div>
      </header>
      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue"
import { useRoute } from "vue-router"
import { useCaseStore } from "./stores/case"

const route = useRoute()
const caseStore = useCaseStore()

const activeMenu = computed(() => {
  if (route.path.startsWith("/research")) return "/research"
  if (route.path.startsWith("/cases")) return "/cases"
  if (route.path.startsWith("/patients")) return "/patients"
  if (route.path.startsWith("/dicom-archive")) return "/dicom-archive"
  return "/"
})

const pageTitle = computed(() => {
  if (route.path.startsWith("/research")) return "IDH 与融合研究"
  if (route.path.startsWith("/cases")) return "病例管理"
  if (route.path.startsWith("/patients")) return "患者管理"
  if (route.path.startsWith("/dicom-archive")) return "隔离 DICOM 研究归档"
  if (route.path.startsWith("/case/")) return "病例详情"
  if (route.path.startsWith("/upload-mri")) return "MRI 影像上传"
  if (route.path.startsWith("/analysis")) return "AI 智能分析"
  if (route.path.startsWith("/report")) return route.query.source === 'dicom' ? 'DICOM 阅片记录' : '诊断报告'
  return "工作台"
})
</script>

<style>
:root {
  --bf-bg: #0b1220;
  --bf-sidebar: #0f172a;
  --bf-panel: #ffffff;
  --bf-border: #e2e8f0;
}

html,
body,
#app {
  height: 100%;
  margin: 0;
  font-family: "Inter", "PingFang SC", "Microsoft YaHei", -apple-system, sans-serif;
  background: #f1f5f9;
  color: #0f172a;
}

.app-shell {
  display: flex;
  height: 100%;
  min-height: 100vh;
}

.sidebar {
  width: 220px;
  flex: none;
  display: flex;
  flex-direction: column;
  background: var(--bf-sidebar);
  color: #e2e8f0;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 16px;
  border-bottom: 1px solid #1e293b;
}

.brand-logo {
  width: 36px;
  height: 36px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: linear-gradient(135deg, #38bdf8, #6366f1);
  color: #fff;
  font-weight: 700;
  font-size: 15px;
}

.brand-name { font-size: 15px; font-weight: 600; color: #f8fafc; }
.brand-sub { font-size: 12px; color: #64748b; }

.side-menu { border-right: none; flex: 1; padding-top: 8px; }
.side-menu .el-menu-item { height: 46px; }
.menu-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.5;
  margin-right: 8px;
}

.sidebar-footer {
  padding: 14px 16px;
  border-top: 1px solid #1e293b;
}
.footer-line { font-size: 12px; color: #94a3b8; }
.footer-sub { font-size: 11px; color: #475569; margin-top: 2px; }

.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.topbar {
  height: 56px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: #fff;
  border-bottom: 1px solid var(--bf-border);
}
.topbar-title { font-size: 16px; font-weight: 600; }
.topbar-right { display: flex; align-items: center; gap: 8px; }

.content {
  flex: 1;
  overflow: auto;
  background: #f1f5f9;
}
</style>
