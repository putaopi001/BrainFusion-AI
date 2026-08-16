<template>


<div class="page">


<h1>
MRI影像上传
</h1>





<el-card>


<template #header>

病例信息

</template>



<p>

病例ID:

{{caseId}}

</p>



</el-card>








<el-card

style="margin-top:20px"

>


<template #header>

选择MRI文件

</template>





<el-upload


:auto-upload="false"


:show-file-list="true"


:limit="1"


:on-change="handleChange"


:before-upload="beforeUpload"



>


<el-button

type="primary"

>

选择MRI文件

</el-button>



</el-upload>








<el-progress

v-if="loading"

:percentage="progress"

/>







<el-button


style="margin-top:20px"


type="success"


@click="uploadMRI"


:loading="loading"



>


上传MRI


</el-button>




</el-card>












<el-card


style="margin-top:20px"


v-if="result"



>


<template #header>

上传结果

</template>





<p>

文件:

{{result.filename}}

</p>




<p>

MRI编号:

{{result.mri_id}}

</p>




<p>

状态:

{{result.case_status}}

</p>





<el-button


type="primary"


@click="goDetail"



>

查看病例详情


</el-button>




</el-card>





</div>


</template>









<script setup>


import {


ref


}

from "vue"



import {


useRoute,


useRouter


}

from "vue-router"



import {


ElMessage


}

from "element-plus"



import request from "../api/axios"






const route = useRoute()


const router = useRouter()






const caseId =

route.params.case_id







const file = ref(null)



const loading = ref(false)



const progress = ref(0)



const result = ref(null)











// =======================
// 文件选择
// =======================


function handleChange(uploadFile){


file.value =

uploadFile.raw



}











// =======================
// 文件检查
// =======================


function beforeUpload(file){



const allow = [

"nii",

"nii.gz",

"dcm"

]



const name=file.name.toLowerCase()



const ok =

allow.some(

x=>name.endsWith(x)

)





if(!ok){


ElMessage.error(

"请选择MRI文件(.nii/.nii.gz/.dcm)"

)


return false


}



return true



}












// =======================
// 上传
// =======================


async function uploadMRI(){



if(!file.value){


ElMessage.warning(

"请选择MRI文件"

)


return


}






const formData =

new FormData()



formData.append(

"file",

file.value

)





loading.value=true



progress.value=30






try{





const res =

await request.post(


`/upload/${caseId}`,


formData,


{

headers:{


"Content-Type":

"multipart/form-data"


}

}



)






progress.value=100






result.value=res.data.data





ElMessage.success(

"MRI上传成功"

)







setTimeout(()=>{


router.push(
{ name:"case-detail", params:{ id:caseId } }

)


},1500)





}

catch(error){



console.log(error)



ElMessage.error(

"MRI上传失败"

)



}



finally{


loading.value=false



}



}









function goDetail(){


router.push(
{ name:"case-detail", params:{ id:caseId } }

)


}



</script>









<style scoped>


.page{


padding:20px;


}



</style>
