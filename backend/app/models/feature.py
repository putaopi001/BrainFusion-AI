from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import ForeignKey

from app.database import Base


class MRIFeature(Base):

    __tablename__="mri_features"


    id=Column(
        Integer,
        primary_key=True,
        index=True
    )


    mri_id=Column(
        Integer,
        ForeignKey("mris.id")
    )


    feature_type=Column(
        String
    )


    feature_data=Column(
        Text
    )