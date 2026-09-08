import os,hmac,hashlib,json,time,csv,io
from pathlib import Path
from urllib.parse import parse_qsl
from fastapi import FastAPI,HTTPException,Header
from fastapi.responses import FileResponse,StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,Field
from database import *
BASE=Path(__file__).parent; TOKEN=os.getenv('BOT_TOKEN','').strip(); DEMO=os.getenv('DEMO_MODE','0')=='1'
app=FastAPI(title='MasterBook API',version='7.0'); app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_methods=['*'],allow_headers=['*'])

def auth(data):
    if not data:
        if DEMO:return 'demo'
        raise HTTPException(401,'Откройте приложение через Telegram')
    if not TOKEN: raise HTTPException(500,'BOT_TOKEN не настроен в Render')
    vals=dict(parse_qsl(data,keep_blank_values=True)); received=vals.pop('hash','')
    check='\n'.join(f'{k}={vals[k]}' for k in sorted(vals))
    secret=hmac.new(b'WebAppData',TOKEN.encode(),hashlib.sha256).digest(); expected=hmac.new(secret,check.encode(),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected,received): raise HTTPException(401,'Недействительные данные Telegram')
    try: age=time.time()-int(vals.get('auth_date','0'))
    except ValueError: age=10**9
    if age>86400: raise HTTPException(401,'Сессия Telegram устарела')
    u=json.loads(vals.get('user','{}')); uid=str(u.get('id') or '')
    if not uid: raise HTTPException(401,'Не удалось определить пользователя Telegram')
    return uid

def uid(h): return auth(h)
def validate_status(status,payment):
    if status not in STATUSES or payment not in PAYMENTS: raise HTTPException(400,'Недопустимый статус')
class Client(BaseModel): name:str=Field(min_length=1,max_length=120); phone:str=''; address:str=''
class Job(BaseModel):
    client_id:int|None=None; service:str=Field(min_length=1,max_length=200); price:float=Field(ge=0); expenses:float=Field(default=0,ge=0); address:str=''; job_date:str; comment:str=''; status:str='done'; payment_status:str='paid'
class Expense(BaseModel): title:str=Field(min_length=1,max_length=200); amount:float=Field(ge=0); expense_date:str; comment:str=''
@app.on_event('startup')
def startup(): init_db()
@app.get('/')
def index(): return FileResponse(BASE/'web'/'index.html')
@app.get('/style.css')
def css(): return FileResponse(BASE/'web'/'style.css',media_type='text/css')
@app.get('/app.js')
def js(): return FileResponse(BASE/'web'/'app.js',media_type='application/javascript')
@app.middleware("http")
async def add_version_header(request, call_next):
    response = await call_next(request)
    response.headers["X-MasterBook-Version"] = "7.0"
    return response

@app.get('/health')
def health():
    return {'status':'ok','version':'7.0','service':'MasterBook'}
@app.get('/api/me')
def me(x_telegram_init_data:str|None=Header(None)): return {'user_id':uid(x_telegram_init_data)}
@app.get('/api/stats')
def stats(period:str='all',x_telegram_init_data:str|None=Header(None)):
    if period not in {'all','month','week'}: raise HTTPException(400,'Invalid period')
    return get_stats(uid(x_telegram_init_data),period)
@app.get('/api/summary')
def summary(x_telegram_init_data:str|None=Header(None)): return get_summary(uid(x_telegram_init_data))
@app.get('/api/clients')
def clients(x_telegram_init_data:str|None=Header(None)): return get_clients(uid(x_telegram_init_data))
@app.post('/api/clients')
def add_client(x:Client,x_telegram_init_data:str|None=Header(None)): return {'id':create_client(uid(x_telegram_init_data),x.name,x.phone,x.address)}
@app.put('/api/clients/{i}')
def edit_client(i:int,x:Client,x_telegram_init_data:str|None=Header(None)):
    if not update_client(uid(x_telegram_init_data),i,x.name,x.phone,x.address): raise HTTPException(404,'Client not found')
    return {'ok':True}
@app.delete('/api/clients/{i}')
def rem_client(i:int,x_telegram_init_data:str|None=Header(None)):
    if not delete_client(uid(x_telegram_init_data),i): raise HTTPException(404,'Client not found')
    return {'ok':True}
@app.get('/api/jobs')
def jobs(limit:int=100,x_telegram_init_data:str|None=Header(None)): return get_jobs(uid(x_telegram_init_data),max(1,min(limit,500)))
@app.post('/api/jobs')
def add_job(x:Job,x_telegram_init_data:str|None=Header(None)):
    u=uid(x_telegram_init_data)
    try: validate_client(u,x.client_id)
    except ValueError: raise HTTPException(400,'Выбранный клиент недоступен')
    validate_status(x.status,x.payment_status); create_job(u,x.client_id,x.service,x.price,x.expenses,x.address,x.job_date,x.comment,x.status,x.payment_status); return {'ok':True}
@app.put('/api/jobs/{i}')
def edit_job(i:int,x:Job,x_telegram_init_data:str|None=Header(None)):
    u=uid(x_telegram_init_data)
    try: validate_client(u,x.client_id)
    except ValueError: raise HTTPException(400,'Выбранный клиент недоступен')
    validate_status(x.status,x.payment_status)
    if not update_job(u,i,x.client_id,x.service,x.price,x.expenses,x.address,x.job_date,x.comment,x.status,x.payment_status): raise HTTPException(404,'Job not found')
    return {'ok':True}
@app.delete('/api/jobs/{i}')
def rem_job(i:int,x_telegram_init_data:str|None=Header(None)):
    if not delete_job(uid(x_telegram_init_data),i): raise HTTPException(404,'Job not found')
    return {'ok':True}
@app.get('/api/expenses')
def expenses(limit:int=100,x_telegram_init_data:str|None=Header(None)): return get_expenses(uid(x_telegram_init_data),max(1,min(limit,500)))
@app.post('/api/expenses')
def add_expense(x:Expense,x_telegram_init_data:str|None=Header(None)): create_expense(uid(x_telegram_init_data),x.title,x.amount,x.expense_date,x.comment); return {'ok':True}
@app.put('/api/expenses/{i}')
def edit_expense(i:int,x:Expense,x_telegram_init_data:str|None=Header(None)):
    if not update_expense(uid(x_telegram_init_data),i,x.title,x.amount,x.expense_date,x.comment): raise HTTPException(404,'Expense not found')
    return {'ok':True}
@app.delete('/api/expenses/{i}')
def rem_expense(i:int,x_telegram_init_data:str|None=Header(None)):
    if not delete_expense(uid(x_telegram_init_data),i): raise HTTPException(404,'Expense not found')
    return {'ok':True}
@app.get('/api/export')
def export_data(x_telegram_init_data:str|None=Header(None)):
    u=uid(x_telegram_init_data); out=io.StringIO(); w=csv.writer(out); w.writerow(['Тип','Дата','Название/Услуга','Клиент','Сумма','Расходы','Статус','Оплата','Комментарий'])
    for j in get_jobs(u,5000): w.writerow(['Работа',j['job_date'],j['service'],j.get('client_name') or '',j['price'],j['expenses'],j.get('status','done'),j.get('payment_status','paid'),j.get('comment','')])
    for e in get_expenses(u,5000): w.writerow(['Расход',e['expense_date'],e['title'],'',-e['amount'],e['amount'],'','',''+(e.get('comment') or '')])
    data=io.BytesIO(('\ufeff'+out.getvalue()).encode('utf-8')); return StreamingResponse(data,media_type='text/csv',headers={'Content-Disposition':'attachment; filename="masterbook-export.csv"'})
@app.get('/api/version')
def api_version():
    return {'version':'7.0','features':['dashboard','backup','telegram-auth-ready','job-status','payment-status','export']}

if __name__=='__main__':
 import uvicorn; uvicorn.run(app,host='0.0.0.0',port=int(os.getenv('PORT','8000')))
