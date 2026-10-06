from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.models.product import Product
from app.schemas.search import SearchFilter, SortOrder


class ProductRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, product: Product) -> Product:
        self.session.add(product)
        self.session.commit()
        self.session.refresh(product)
        return product

    def get_by_id(self, product_id: UUID) -> Product | None:
        return self.session.query(Product).filter(Product.id == product_id).first()

    def get_by_external_id(self, external_product_id: str) -> Product | None:
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
            .order_by(desc(Product.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
        return products, total

    def list_available(
        self,
        filters: SearchFilter,
        sort: SortOrder = SortOrder.RELEVANCE,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Product], int]:
        """List available products matching exact-value filters, with sorting and pagination."""
        query = self.session.query(Product).filter(Product.availability == True)
        for field in ("category", "gender", "color", "season"):
            value = getattr(filters, field)
            if value is not None:
                query = query.filter(getattr(Product, field) == value)

        total = query.count()
        if sort == SortOrder.NEWEST:
            # Some years are stored as floats ("2017.0"), so sort as a number, not an integer.
            order = (Product.attributes["year"].as_float().desc().nulls_last(), Product.id)
        elif sort == SortOrder.NAME:
            order = (Product.name, Product.id)
        else:
            order = (desc(Product.created_at), Product.id)
        products = query.order_by(*order).offset(skip).limit(limit).all()
        return products, total

    def list_all(self, skip: int = 0, limit: int = 100) -> tuple[list[Product], int]:
        """List all products with pagination."""
        total = self.session.query(Product).count()
        products = (
            self.session.query(Product)
            .order_by(desc(Product.created_at))
            .offset(skip)
            .limit(limit)
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