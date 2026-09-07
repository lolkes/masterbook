import os
from pathlib import Path
from fastapi import FastAPI,HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from database import *
BASE=Path(__file__).parent; app=FastAPI(title='MasterBook API'); app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_methods=['*'],allow_headers=['*'])
class Client(BaseModel): name:str; phone:str=''; address:str=''
class Job(BaseModel): client_id:int|None=None; service:str; price:float; expenses:float=0; address:str=''; job_date:str; comment:str=''
class Expense(BaseModel): title:str; amount:float; expense_date:str; comment:str=''
@app.on_event('startup')
def startup(): init_db()
@app.get('/')
def index(): return FileResponse(BASE/'web'/'index.html')
@app.get('/style.css')
def css(): return FileResponse(BASE/'web'/'style.css',media_type='text/css')
@app.get('/app.js')
def js(): return FileResponse(BASE/'web'/'app.js',media_type='application/javascript')
@app.get('/health')
def health(): return {'status':'ok'}
@app.get('/api/stats')
def stats(): return get_stats()
@app.get('/api/clients')
def clients(): return get_clients()
@app.get('/api/jobs')
def jobs(): return get_jobs()
@app.post('/api/clients')
def add_client(x:Client):
    if not x.name.strip(): raise HTTPException(400,'Client name is required')
    return {'id':create_client(x.name,x.phone,x.address)}
@app.post('/api/jobs')
def add_job(x:Job):
    if not x.service.strip() or x.price<0 or x.expenses<0: raise HTTPException(400,'Invalid job data')
    create_job(x.client_id,x.service,x.price,x.expenses,x.address,x.job_date,x.comment); return {'ok':True}
@app.post('/api/expenses')
def add_expense(x:Expense):
    if not x.title.strip() or x.amount<0: raise HTTPException(400,'Invalid expense data')
    create_expense(x.title,x.amount,x.expense_date,x.comment); return {'ok':True}
if __name__=='__main__':
 import uvicorn; uvicorn.run(app,host='0.0.0.0',port=int(os.getenv('PORT','8000')))
