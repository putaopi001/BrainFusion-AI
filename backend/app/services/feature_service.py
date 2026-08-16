import json
import nibabel as nib


from app.database import SessionLocal
from app.models.feature import MRIFeature



# =====================================
# MRI Feature Extraction
# =====================================


def extract_mri_feature(filepath:str):

    """
    MRI基础特征提取

    当前:
    baseline feature

    未来:
    MedNeXt / nnUNet 输入接口

    """

    try:

        img = nib.load(filepath)

        data = img.get_fdata()



        feature = {

            "shape":
            list(data.shape),


            "mean":
            float(data.mean()),


            "std":
            float(data.std()),


            "voxel_number":
            int(data.size),


            "datatype":
            str(data.dtype)

        }


        return feature



    except Exception as e:


        return {

            "error":
            str(e)

        }





# =====================================
# MRI Loader
# =====================================


def load_mri(filepath:str):


    img = nib.load(filepath)


    data = img.get_fdata()


    return data





# =====================================
# Save Feature
# =====================================


def save_mri_feature(
    mri_id:int,
    feature:dict
):


    db=SessionLocal()



    try:


        record=MRIFeature(


            mri_id=mri_id,


            feature_type=
            "MRI_baseline_feature",


            feature_data=
            json.dumps(
                feature
            )

        )


        db.add(record)

        db.commit()

        db.refresh(record)


        return record.id



    finally:


        db.close()