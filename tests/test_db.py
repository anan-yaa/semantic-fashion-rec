import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, get_session
from app.db.models.product import Product
from app.db.repositories.product_repository import ProductRepository


def test_create_and_read_product():
    """Test basic product CRUD through the repository."""
    engine = create_engine(
        "postgresql+psycopg2://fashion_rec:dev_password@localhost:5432/fashion_rec",
    )

    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with SessionLocal() as session:
        repo = ProductRepository(session)

        product = Product(
            id="prod-001",
            external_product_id="ext-001",
            name="Test Jacket",
            description="A test jacket for unit testing",
            category="jackets",
            subcategory="outerwear",
            brand="TestBrand",
            gender="male",
            color="blue",
            material="cotton",
            style="casual",
            season="spring",
            price=99.99,
            currency="USD",
            availability=True,
        )

        created = repo.create(product)
        assert created.id == "prod-001"
        assert created.name == "Test Jacket"

        retrieved = repo.get_by_id("prod-001")
        assert retrieved is not None
        assert retrieved.name == "Test Jacket"

        read_by_ext = repo.get_by_external_id("ext-001")
        assert read_by_ext is not None
        assert read_by_ext.id == "prod-001"

        active = repo.list_active()
        assert len(active) >= 1

        found = repo.search_by_name("Jacket")
        assert len(found) >= 1

        # Update
        created.description = "Updated description"
        updated = repo.update(created)
        assert updated.description == "Updated description"

        # Delete
        repo.delete(updated)
        after_delete = repo.get_by_id("prod-001")
        assert after_delete is None

    print("All database tests passed!")


if __name__ == "__main__":
    test_create_and_read_product()