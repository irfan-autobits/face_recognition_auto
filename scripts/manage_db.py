# scripts/manage_db.py
from app.models.model import db, Detection, Camera, FaceRecogUser
from sqlalchemy.exc import ProgrammingError
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.orm import sessionmaker
from config.paths import IS_RM_REPORT

def manage_table(purge=False, drop=False, spec=False):
    try:
        if purge:
            # Delete all data if the table exists
            db.session.query(Detection).delete()
            db.session.commit()
            print("Purged all rows in the Detection table.")
        elif spec:
            # Drop the specific table
            # Camera.__table__.drop(db.engine)
            # db.session.commit()
            # FaceRecogUser.__table__.drop(db.engine)
            if IS_RM_REPORT:
                Detection.__table__.drop(db.engine)
            db.session.commit()
            db.create_all()
            # print("Dropped Camera and FaceRecogUser but not Detection and Embedding.")
            print("Dropped FaceRecogUser but not Detection and Embedding.")
        elif drop:
            db.drop_all()
            db.create_all()
            print("Dropped all the table.")
        else:
            # Ensure the table exists
            db.create_all()
            print("Created all the table if it didn't exist.")
    except ProgrammingError:
        print("The table does not exist yet.")  

def import_tab(db_url):
        # Create database engine
        engine = create_engine(db_url)
        metadata = MetaData()
        metadata.reflect(bind=engine)

        # Load specific tables
        global subject_table, embedding_table, session
        subject_table = Table('subject', metadata, autoload_with=engine)
        embedding_table = Table('embedding', metadata, autoload_with=engine)

        # Create a session
        Session = sessionmaker(bind=engine)
        session = Session()