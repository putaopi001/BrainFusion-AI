import SimpleITK as sitk

import numpy as np

import os




def preprocess_mri(
        file_path:str
):


    image=sitk.ReadImage(

        file_path

    )



    data=sitk.GetArrayFromImage(

        image

    ).astype(

        np.float32

    )




    mean=float(

        data.mean()

    )


    std=float(

        data.std()

    )




    normalized=(

        data-mean

    )/(

        std+1e-8

    )





    # =====================
    # 保存路径
    # =====================


    os.makedirs(

        "processed",

        exist_ok=True

    )



    filename=os.path.basename(

        file_path

    )



    if filename.endswith(".nii.gz"):


        new_name=filename.replace(

            ".nii.gz",

            "_preprocess.nii.gz"

        )


    else:


        new_name=filename.replace(

            ".nii",

            "_preprocess.nii"

        )




    output_path=os.path.join(

        "processed",

        new_name

    )





    new_image=sitk.GetImageFromArray(

        normalized

    )


    new_image.CopyInformation(

        image

    )



    sitk.WriteImage(

        new_image,

        output_path

    )





    return {


        "original_path":

        file_path,



        "processed_path":

        output_path,



        "shape":

        list(

            normalized.shape

        ),



        "spacing":

        list(

            image.GetSpacing()

        ),



        "mean":

        mean,



        "std":

        std,



        "voxel_number":

        int(

            normalized.size

        )

    }