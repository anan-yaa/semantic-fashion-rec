from typing import Optional
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.models.product import Product


class ProductRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, product: Product) -> Product:
        self.session.add(product)
        self.session.commit()
        self.session.refresh(product)
        return product

    def get_by_id(self, product_id: UUID) -> Optional[Product]:
        return self.session.query(Product).filter(Product.id == product_id).first()

    def get_by_external_id(self, external_product_id: str) -> Optional[Product]:
        return (
            self.session.query(Product)
            .filter(Product.external_product_id == external_product_id)
            .first()
        )

    def list_active(
        self, skip: int = 0, limit: int = 100
    ) -> tuple[list[Product], int]:
        """List active products with pagination."""
        total = self.session.query(Product).filter(Product.availability == True).count()
        products = (
            self.session.query(Product)
            .filter(Product.availability == True)
            .offset(skip)
            .limit(limit)
            .all()
        )
        return products, total

    def list_all(self, skip: int = 0, limit: int = 100) -> tuple[list[Product], int]:
        """List all products with pagination."""
        total = self.session.query(Product).count()
        products = (
            self.session.query(Product)
            .offset(skip)
            .limit(limit)
            .order_by(desc(Product.created_at))
            .all()
        )
        return products, total

    def search_by_name(self, name: str, limit: int = 50) -> list[Product]:
        return (
            self.session.query(Product)
            .filter(Product.name.ilike(f"%{name}%"))
            .limit(limit)
            .all()
        )

    def search_by_category(self, category: str, limit: int = 50) -> list[Product]:
        return (
            self.session.query(Product)
            .filter(Product.category == category)
            .limit(limit)
            .all()
        )

    def update(self, product: Product) -> Product:
        self.session.add(product)
        self.session.commit()
        self.session.refresh(product)
        return product

    def delete(self, product: Product) -> None:
        self.session.delete(product)
        self.session.commit()

    def upsert_many(self, products: list[Product]) -> int:
        """
        Upsert multiple products without per-row commits.
        Uses external_product_id for conflict resolution.
        Returns the number of products upserted.
        """
        for product in products:
            self.session.merge(product)
        self.session.commit()
        return len(products)

    def get_unembed_count(self) -> int:
        """Count products without embeddings."""
        return (
            self.session.query(Product)
            .filter(Product.embedding == None)
            .count()
        )