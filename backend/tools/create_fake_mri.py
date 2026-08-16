import numpy as np
import nibabel as nib
import os


# 模拟三维脑MRI
data = np.random.rand(
    128,
    128,
    64
)


# 创建脑部仿射矩阵
affine = np.eye(4)


img = nib.Nifti1Image(
    data,
    affine
)


os.makedirs(
    "fake_data",
    exist_ok=True
)


path = "fake_data/fake_brain.nii.gz"


nib.save(
    img,
    path
)


print(
    "MRI created:",
    path
)