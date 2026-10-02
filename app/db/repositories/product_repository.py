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

    def get_by_id(self, product_id: str) -> Product | None:
        return self.session.query(Product).filter(Product.id == product_id).first()

    def get_by_external_id(self, external_product_id: str) -> Product | None:
        return (
            self.session.query(Product)
            .filter(Product.external_product_id == external_product_id)
            .first()
        )

    def list_active(self) -> list[Product]:
        return (
            self.session.query(Product)
            .filter(Product.availability == True)
            .all()
        )

    def search_by_name(self, name: str) -> list[Product]:
        return (
            self.session.query(Product)
            .filter(Product.name.ilike(f"%{name}%"))
            .all()
        )

    def search_by_category(self, category: str) -> list[Product]:
        return (
            self.session.query(Product)
            .filter(Product.category == category)
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