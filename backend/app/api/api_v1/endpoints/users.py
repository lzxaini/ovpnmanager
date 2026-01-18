from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud
from app.api import deps
from app.api.security import get_current_user
from app.schemas.user import User, UserCreate, UserUpdate

router = APIRouter()


def ensure_superuser(user=Depends(get_current_user)):
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough privileges")
    return user


@router.get("/", response_model=list[User], dependencies=[Depends(ensure_superuser)])
def list_users(db: Session = Depends(deps.get_db)):
    # 查询用户列表（仅超级管理员）
    return crud.user.get_multi(db)


@router.post("/", response_model=User, status_code=status.HTTP_201_CREATED, dependencies=[Depends(ensure_superuser)])
def create_user(
    user_in: UserCreate,
    db: Session = Depends(deps.get_db),
):
    # 创建用户（仅超级管理员）
    existing = crud.user.get_by_username(db, username=user_in.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    return crud.user.create(db, user_in)


@router.patch("/{user_id}", response_model=User, dependencies=[Depends(ensure_superuser)])
def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(deps.get_db),
):
    # 更新用户（仅超级管理员）
    db_obj = crud.user.get(db, user_id)
    if not db_obj:
        raise HTTPException(status_code=404, detail="User not found")
    return crud.user.update(db, db_obj=db_obj, obj_in=user_in)


@router.delete("/{user_id}", response_model=User, dependencies=[Depends(ensure_superuser)])
def delete_user(user_id: int, db: Session = Depends(deps.get_db)):
    # 删除用户（仅超级管理员）
    db_obj = crud.user.remove(db, user_id)
    if not db_obj:
        raise HTTPException(status_code=404, detail="User not found")
    return db_obj
