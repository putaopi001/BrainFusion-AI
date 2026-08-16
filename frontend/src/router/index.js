import {
    createRouter,
    createWebHistory
} from "vue-router"



import Home from "../views/Home.vue"
import Patients from "../views/Patients.vue"
import Cases from "../views/Cases.vue"
import Analysis from "../views/Analysis.vue"
import Report from "../views/Report.vue"
import UploadMRI from "../views/UploadMRI.vue"
import CaseDetail from "../views/CaseDetail.vue"
import Workstation from "../views/Workstation.vue"



const routes=[



{
    path:"/",
    component:Home
},




{
    path:"/patients",
    component:Patients
},




{
    path:"/cases",
    component:Cases
},




{
    path:"/analysis",
    component:Analysis
},




{
    path:"/report",
    component:Report
},




{
    path:"/case/:id",
    name:"case-detail",
    component:CaseDetail
},




{
    path:"/upload-mri/:case_id",
    name:"upload-mri",
    component:UploadMRI
},




{
    path:"/workstation/:id",
    name:"workstation",
    component:Workstation
}




]





const router=createRouter({


    history:createWebHistory(),


    routes


})





export default router
