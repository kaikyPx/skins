from dataclasses import dataclass

@dataclass
class SkinItem:
    site: str
    name: str
    float_value: float
    price: float
    url: str
    image_url: str = ""
    percentage: int = 0

    def __str__(self):
        return f"[{self.site}] {self.name} | Float: {self.float_value} | Preço: $ {self.price}"
