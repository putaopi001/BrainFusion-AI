"""Narrow local login for review attribution; no public account provisioning."""
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, SecretStr
from app.services import local_auth as auth

class PrivateValidationRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def private_handler(request):
            try:
                return await handler(request)
            except RequestValidationError:
                raise HTTPException(422, '登录字段格式不正确。') from None
        return private_handler

router = APIRouter(prefix='/local-auth', tags=['local-auth'], route_class=PrivateValidationRoute)
class Login(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str
    password: SecretStr

@router.get('/session')
def current(request: Request, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    users, _ = auth.accounts()
    record = auth.session(request)
    return dict(code=200, data=dict(configured=bool(users), user=record['user'] if record else None,
        csrf=record['csrf'] if record else None, session_scope='review_only_single_process_loopback',
        professional_credential_verified=False))

@router.post('/login')
def login(payload: Login, request: Request, response: Response):
    token = auth.login(request, payload.username, payload.password.get_secret_value())
    response.set_cookie(auth.COOKIE, token, max_age=auth.SESSION_SECONDS, httponly=True, samesite='strict',
                        secure=request.url.scheme == 'https', path='/')
    response.headers['Cache-Control'] = 'no-store'
    return dict(code=200, data=dict(logged_in=True))

@router.post('/logout')
def logout(request: Request, response: Response):
    auth.logout(request)
    response.delete_cookie(auth.COOKIE, path='/', httponly=True, samesite='strict')
    response.headers['Cache-Control'] = 'no-store'
    return dict(code=200, data=dict(logged_out=True))
