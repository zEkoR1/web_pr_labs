from sqlalchemy import Column, Integer, String, Float, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


# Data Model
class Product(Base):
    __tablename__ = 'products'

    id = Column(Integer, primary_key=True)
    name = Column(String(80), unique=True, nullable=False)
    url = Column(String(200), nullable=False)
    price_mdl = Column(Float, nullable=False)
    display_size = Column(String(50), nullable=False)
    price_eur = Column(Float, nullable=False)

    def to_dict(self):
        """Convert the Product instance into a dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'url': self.url,
            'price_mdl': self.price_mdl,
            'display_size': self.display_size,
            'price_eur': self.price_eur
        }


# Database setup
engine = create_engine('sqlite:///products.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
