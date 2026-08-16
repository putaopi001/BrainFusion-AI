import nibabel as nib


img = nib.load(
    "fake_data/fake_brain.nii.gz"
)


print(
    "shape:",
    img.shape
)


print(
    "datatype:",
    img.get_data_dtype()
)