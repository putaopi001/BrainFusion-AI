<template>


<div class="page">


<h1>
患者管理
</h1>



<el-card>


<h2>
新增患者
</h2>


<el-form>


<el-form-item label="姓名">

<el-input
v-model="form.name"
/>

</el-form-item>



<el-form-item label="年龄">

<el-input
v-model="form.age"
/>

</el-form-item>



<el-form-item label="性别">


<el-select
v-model="form.gender"
>


<el-option
label="male"
value="male"
/>


<el-option
label="female"
value="female"
/>


</el-select>


</el-form-item>



<el-button

type="primary"

@click="createPatient"

>

创建患者

</el-button>


</el-form>


</el-card>





<el-card
style="margin-top:20px"
>


<h2>
患者列表
</h2>



<el-button
@click="loadPatients"
>

刷新

</el-button>




<el-table

:data="patients"

style="margin-top:20px"

>


<el-table-column
prop="id"
label="ID"
/>


<el-table-column
prop="name"
label="姓名"
/>


<el-table-column
prop="age"
label="年龄"
/>


<el-table-column
prop="gender"
label="性别"
/>



</el-table>



</el-card>



</div>


</template>





<script setup>


import {
ref,
onMounted
} from "vue"



import { ElMessage } from "element-plus"
import request from "../api/axios"




const patients=ref([])



const form=ref({

name:"",

age:"",

gender:"male"

})






async function loadPatients(){


const res =
await request.get(

"/patients/"

)


patients.value=res.data.data || []


}






async function createPatient(){



await request.post(

"/patients/",

{

name:
form.value.name,


age:
Number(form.value.age),


gender:
form.value.gender


}

)



ElMessage.success(
"患者创建成功"
)



form.value={

name:"",

age:"",

gender:"male"

}



loadPatients()


}





onMounted(()=>{


loadPatients()


})



</script>