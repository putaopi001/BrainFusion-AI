import { createRouter, createWebHistory } from "vue-router"
import Home from "../views/Home.vue"

const routes = [
  { path: '/', component: Home },
  { path: '/patients', component: () => import('../views/Patients.vue') },
  { path: '/cases', component: () => import('../views/Cases.vue') },
  { path: '/analysis', component: () => import('../views/Analysis.vue') },
  { path: '/report', component: () => import('../views/Report.vue') },
  { path: '/research', component: () => import('../views/Research.vue') },
  { path: '/dicom-archive', component: () => import('../views/DicomArchive.vue') },
  { path: '/case/:id', name: 'case-detail', component: () => import('../views/CaseDetail.vue') },
  { path: '/upload-mri/:case_id', name: 'upload-mri', component: () => import('../views/UploadMRI.vue') },
  { path: '/workstation/:id', name: 'workstation', component: () => import('../views/Workstation.vue') },
]

export default createRouter({ history: createWebHistory(), routes })
