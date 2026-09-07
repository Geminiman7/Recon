from sqlalchemy.orm import Session
from app.models.processor import Processor


class ProcessorService:

    @staticmethod
    def create_processor(db, request):
        existing = db.query(Processor).filter(
            Processor.name == request.name
        ).first()

        if existing:
            raise ValueError("Processor name already exists.")

        processor = Processor(
            name=request.name,
            description=request.description
        )

        db.add(processor)
        db.commit()
        db.refresh(processor)

        return processor

    @staticmethod
    def list_processors(db):
        return db.query(Processor).filter(Processor.is_active == True).all()
