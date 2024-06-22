from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware

from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache

from redis import asyncio as aioredis

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

import json
import accountManager
from go_cardless import GoCardlessClient

with open("secrets.json", "r") as f:
    secrets = json.loads(f.read())

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None
    account_url: str

class UserInDB(User):
    hashed_password: str


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:58666",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@cache()
async def get_cache():
    return 1

@app.on_event("startup")
async def startup():
   redis = aioredis.from_url("redis://localhost", encoding="utf8", decode_responses=True)
   FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)


def authenticate_user(fake_db, username: str, password: str):
    user = get_user(fake_db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, secrets["SECRET_KEY"], algorithm=secrets["ALGORITHM"])
    return encoded_jwt


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, secrets["SECRET_KEY"], algorithms=[secrets["ALGORITHM"]])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(secrets["users_db"], username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


@app.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    user = authenticate_user(secrets["users_db"], form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=secrets["ACCESS_TOKEN_EXPIRE_MINUTES"])
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")

@app.get("/accounts")
@cache()
def read_accounts(
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    return accountManager.getAccountRecords(current_user.account_url)

@app.get("/accounts/by_name/{account_name}")
@cache()
def read_accounts_by_name(
    current_user: Annotated[User, Depends(get_current_active_user)],
    account_name: str = None
):
    return accountManager.getAccountRecord(current_user.account_url, name=account_name)

@app.get("/accounts/by_guid/{account_guid}")
@cache()
def read_accounts_by_guid(
    current_user: Annotated[User, Depends(get_current_active_user)],
    account_guid: str = None
):
    return accountManager.getAccountRecord(current_user.account_url, guid=account_guid)

@app.get("/accounts/update")
def update_accounts(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    client = GoCardlessClient(current_user.account_url)
    client.update_accounts()

    FastAPICache.clear()

    return {"status": "OK"}


@app.on_event("shutdown")
async def shutdown_event():
    accountManager.shutdown()
