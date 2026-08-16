<template>

<div class="page">


<h1>
BrainFusion AI 诊断报告
</h1>




<!-- =========================
使用声明
========================= -->

<el-card style="margin-top:20px">


<template #header>
使用声明
</template>


<p>
本报告由 BrainFusion-AI 教学原型系统自动生成，仅用于教学与原型演示，不构成临床诊断或治疗建议；最终判断请以具有执业资质的医生阅片意见为准。
</p>


</el-card>




<!-- =========================
病例信息
========================= -->

<el-card>


<template #header>
病例信息
</template>



<p>
病例编号:
{{caseId}}
</p>



<el-button
type="primary"
@click="loadReport"
>
刷新报告
</el-button>


</el-card>







<!-- =========================
风险评估
========================= -->


<el-card
style="margin-top:20px"
>


<template #header>
综合风险评估
</template>



<div class="risk-box">


<h1
:class="riskClass"
>

{{riskText}}

</h1>



<p>

风险等级：

<el-tag
:type="tagType"
>

{{riskText}}

</el-tag>


</p>


</div>


</el-card>








<!-- =========================
AI指标
========================= -->


<el-card
style="margin-top:20px"
>


<template #header>

AI多模态分析结果

</template>





<el-row
:gap="20"
>



<el-col
:span="8"
>


<el-card>

<h3>
MRI影像模型
</h3>


<p>

模型:

MRI Baseline Model

</p>


<p>

肿瘤概率:

{{mriProbability}}

</p>


<el-progress

:percentage="mriPercent"

/>


</el-card>



</el-col>









<el-col
:span="8"
>


<el-card>


<h3>
临床模型
</h3>



<p>

模型:

TabICL-v2

</p>



<p>

风险评分:

{{clinicalScore}}

</p>


<el-progress

:percentage="clinicalPercent"

/>


</el-card>


</el-col>









<el-col
:span="8"
>


<el-card>


<h3>
融合模型
</h3>



<p>

模型:

Multi-modal Fusion

</p>



<p>

融合评分:

{{fusionScore}}

</p>



<el-progress

:percentage="fusionPercent"

/>


</el-card>


</el-col>



</el-row>




</el-card>










<!-- =========================
Agent总结
========================= -->


<el-card
style="margin-top:20px"
>


<template #header>

AI多模态分析总结

</template>



<el-timeline>



<el-timeline-item

v-for="item in summary"

:key="item"

>

{{item}}


</el-timeline-item>



</el-timeline>




</el-card>









<!-- =========================
建议
========================= -->



<el-card

style="margin-top:20px"

>


<template #header>

Agent智能建议

</template>




<el-alert

v-for="item in recommendation"

:key="item"

:title="item"

type="warning"

show-icon

style="margin-bottom:10px"

/>




</el-card>









<!-- =========================
报告信息
========================= -->


<el-card

style="margin-top:20px"

>


<template #header>

报告信息

</template>



<p>

模型版本:

{{modelVersion}}

</p>



<p>

生成时间:

{{time}}

</p>



</el-card>






</div>


</template>









<script setup>


import {

ref,

computed,

onMounted

}

from "vue"



import {

useRoute

}

from "vue-router"



import request from "../api/axios"





const route = useRoute()



const caseId = computed(()=>String(route.query.case_id || ""))







const report =
ref({})


const modelVersion =
ref("未记录")



const summary =
ref([])



const recommendation =
ref([])



const time =
ref("")





// =======================
// AI指标
// =======================


const mriProbability =
ref(0)



const clinicalScore =
ref(0)



const fusionScore =
ref(0)








async function loadReport(){


if(!caseId.value){

return

}


try{



const res =
await request.get(

`/cases/${caseId.value}/detail`

)



const data =
res.data.data



console.log(
"REPORT DATA",
data
)




report.value =
data.report || {}


modelVersion.value =
data.prediction?.model_version || "未记录"


summary.value=[]

recommendation.value=[]





if(data.report?.summary){


summary.value =
JSON.parse(
data.report.summary
)


}





if(data.report?.recommendation){


recommendation.value =
JSON.parse(
data.report.recommendation
)


}







// =====================
// 从prediction读取AI结果
// =====================


if(data.prediction){


mriProbability.value =
Number(
data.prediction.tumor_probability
)



clinicalScore.value =
Number(
data.prediction.risk_score
)



fusionScore.value =
Number(
data.prediction.fusion_score
)


}




time.value =
data.report?.created_time
? new Date(data.report.created_time).toLocaleString()
: "未记录"



}



catch(e){


console.log(
"report error",
e
)


}



}









// 百分比转换


const mriPercent =
computed(()=>{


return Math.round(
mriProbability.value*100
)


})





const clinicalPercent =
computed(()=>{


return Math.round(
clinicalScore.value*100
)


})





const fusionPercent =
computed(()=>{


return Math.round(
fusionScore.value*100
)


})










// 风险文字


const riskText =
computed(()=>{


switch(
report.value.risk_level
){


case "high":

return "高风险"



case "medium":

return "中风险"



case "low":

return "低风险"



default:

return "未知"



}


})









const riskClass =
computed(()=>{


return {


high:
report.value.risk_level==="high",



low:
report.value.risk_level==="low",



medium:
report.value.risk_level==="medium"


}


})








const tagType =
computed(()=>{


if(
report.value.risk_level==="high"
)

return "danger"



if(
report.value.risk_level==="medium"
)

return "warning"



return "success"



})







onMounted(()=>{


loadReport()


})



</script>









<style scoped>


.page{


padding:20px;


}





.risk-box{


text-align:center;


padding:20px;


}





.high{


color:#f56c6c;


}





.medium{


color:#e6a23c;


}





.low{


color:#67c23a;


}



</style>
