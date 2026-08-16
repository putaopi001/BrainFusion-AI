from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Float

from app.database import Base



class Clinical(Base):

    __tablename__="clinical_features"



    id = Column(
        Integer,
        primary_key=True,
        index=True
    )


    case_id = Column(
        Integer,
        index=True
    )


    age = Column(
        Integer
    )


    gender = Column(
        String
    )


    IDH_status = Column(
        String,
        nullable=True
    )


    MGMT_status = Column(
        String,
        nullable=True
    )


    Ki67 = Column(
        Float,
        nullable=True
    )