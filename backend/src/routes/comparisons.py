from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.controllers.dependencies import current_user,writers
from src.schemas.comparison import ComparisonInput
from src.services import comparisons
router=APIRouter()
@router.get('/comparisons')
def index(db:Session=Depends(get_db),user=Depends(current_user)):return comparisons.list_comparisons(db)
@router.get('/comparisons/{id}')
def detail(id:int,db:Session=Depends(get_db),user=Depends(current_user)):return comparisons.get_comparison(db,id)
@router.post('/comparisons',status_code=201)
def create(data:ComparisonInput,db:Session=Depends(get_db),user=Depends(writers)):return comparisons.create_or_recompute(db,data,user)
@router.post('/comparisons/{id}/refresh')
def refresh(id:int,db:Session=Depends(get_db),user=Depends(writers)):return comparisons.refresh_stale(db,id,user)
