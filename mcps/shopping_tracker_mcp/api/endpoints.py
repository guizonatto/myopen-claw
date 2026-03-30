from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from db.models import Compra, Wishlist, get_session
from typing import List
from auth import verify_api_key

router = APIRouter(dependencies=[Depends(verify_api_key)])

class CompraInput(BaseModel):
    nome: str
    quantidade: float
    unidade: str = "unidade"
    wishlist: bool = False
    preco: float | None = None
    loja: str | None = None
    marca: str | None = None
    volume_embalagem: str | None = None

@router.post("/compras")
def registrar_compra(compras: List[CompraInput]):
    try:
        with get_session() as session:
            for item in compras:
                compra = Compra(
                    nome=item.nome,
                    quantidade=item.quantidade,
                    unidade=item.unidade,
                    wishlist=item.wishlist,
                    preco=item.preco,
                    loja=item.loja,
                    marca=item.marca,
                    volume_embalagem=item.volume_embalagem
                )
                session.add(compra)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/wishlist")
def listar_wishlist():
    with get_session() as session:
        items = session.query(Wishlist).all()
        return [item.to_dict() for item in items]
