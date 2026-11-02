from pathlib import Path
from datetime import datetime, date, timedelta
import sqlite3, csv, io, os
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE = Path(__file__).parent
DB = BASE / 'data' / 'atelier.db'
UPLOADS = BASE / 'uploads'
UPLOADS.mkdir(exist_ok=True)
DB.parent.mkdir(exist_ok=True)
app = FastAPI(title='ATELIER TMS API', version='1.0.0', description='Backend de démonstration pour commissionnaire de transport')

STATUSES = {'À affecter','Planifiée','En cours','Livrée','Incident'}

def conn():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c

def init_db():
    with conn() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT UNIQUE NOT NULL, client TEXT NOT NULL, origin TEXT NOT NULL, destination TEXT NOT NULL, goods TEXT NOT NULL, vehicle TEXT, pickup_date TEXT, amount REAL DEFAULT 0, carrier_id INTEGER, status TEXT NOT NULL DEFAULT 'À affecter', notes TEXT DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY(carrier_id) REFERENCES carriers(id));
        CREATE TABLE IF NOT EXISTS carriers(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, zone TEXT, fleet INTEGER DEFAULT 0, punctuality REAL DEFAULT 95, rating REAL DEFAULT 4.5, cost REAL DEFAULT 0, available INTEGER DEFAULT 1, phone TEXT DEFAULT '', email TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS tenders(id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT UNIQUE, shipper TEXT, origin TEXT, destination TEXT, vehicle TEXT, deadline TEXT, offers INTEGER DEFAULT 0, status TEXT DEFAULT 'Ouvert', description TEXT DEFAULT '', created_at TEXT);
        CREATE TABLE IF NOT EXISTS incidents(id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER, category TEXT, severity TEXT, description TEXT, status TEXT DEFAULT 'Ouvert', created_at TEXT, resolved_at TEXT, FOREIGN KEY(order_id) REFERENCES orders(id));
        CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER, name TEXT, kind TEXT, filename TEXT, uploaded_at TEXT, FOREIGN KEY(order_id) REFERENCES orders(id));
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER, label TEXT, details TEXT, created_at TEXT, FOREIGN KEY(order_id) REFERENCES orders(id));
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
        ''')
        if c.execute('SELECT COUNT(*) FROM carriers').fetchone()[0] == 0:
            c.executemany('INSERT INTO carriers(name,zone,fleet,punctuality,rating,cost,available,phone,email) VALUES(?,?,?,?,?,?,?,?,?)',[
              ('Maroc Transit','National',24,98,4.9,2150,1,'0522001100','ops@maroc-transit.demo'),('North Cargo','Nord / Centre',16,96,4.8,2300,1,'0539002200','contact@northcargo.demo'),('LogiTrans','National',31,93,4.6,1980,1,'0522003300','dispatch@logitrans.demo'),('Atlas Fret','Sud / Centre',12,91,4.4,2050,0,'0522004400','contact@atlasfret.demo'),('Rapid Route','National',19,95,4.7,2200,1,'0522005500','ops@rapidroute.demo')])
        if c.execute('SELECT COUNT(*) FROM orders').fetchone()[0] == 0:
            now=datetime.now().isoformat(timespec='seconds')
            rows=[('TR-2026-0842','Atlas Distribution','Casablanca','Tanger','Produits alimentaires','Camion 12T','2026-11-03',6800,1,'En cours','Livraison en transit'),('TR-2026-0841','Novatek Industrie','Rabat','Marrakech','Équipements industriels','Camion 12T','2026-11-03',7400,None,'À affecter','Commande prioritaire'),('TR-2026-0840','Soremed','Kénitra','Agadir','Produits emballés','Frigorifique','2026-11-04',8900,3,'Planifiée','Température contrôlée'),('TR-2026-0839','ElectroPro','Tanger','Fès','Matériel électrique','Fourgon','2026-11-02',4200,2,'Incident','Retard signalé'),('TR-2026-0838','Atlas Distribution','Casablanca','Rabat','Marchandise générale','Camion 12T','2026-11-02',3100,1,'Livrée','Réception confirmée'),('TR-2026-0837','MecaParts','Casablanca','Agadir','Pièces automobiles','Semi-remorque','2026-11-04',9600,None,'À affecter',''),('TR-2026-0836','BioSanté','Fès','Meknès','Produits pharmaceutiques','Frigorifique','2026-11-05',3600,3,'Planifiée',''),('TR-2026-0835','Soremed','Fès','Tanger','Produits médicaux','Frigorifique','2026-11-04',5300,None,'À affecter','')]
            for r in rows:
                c.execute('INSERT INTO orders(ref,client,origin,destination,goods,vehicle,pickup_date,amount,carrier_id,status,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(*r,now,now))
            c.execute("INSERT INTO incidents(order_id,category,severity,description,status,created_at) VALUES(4,'Retard','Moyenne','Retard estimé à 2 heures sur le trajet Tanger–Fès.','Ouvert',?)",(now,))
            c.execute("INSERT INTO tenders(ref,shipper,origin,destination,vehicle,deadline,offers,status,description,created_at) VALUES('AO-26091','Atlas Distribution','Casablanca','Tanger','Camion 12T','2026-11-03',4,'Ouvert','Transport de marchandises palettisées',?)",(now,))
            c.execute("INSERT INTO tenders(ref,shipper,origin,destination,vehicle,deadline,offers,status,description,created_at) VALUES('AO-26090','Novatek Industrie','Rabat','Fès','Semi-remorque','2026-11-04',2,'Consultation','Équipements industriels',?)",(now,))
            c.execute("INSERT INTO tenders(ref,shipper,origin,destination,vehicle,deadline,offers,status,description,created_at) VALUES('AO-26089','Soremed','Kénitra','Agadir','Frigorifique','2026-11-05',5,'À comparer','Produits sous température dirigée',?)",(now,))
            for key,val in [('company','ATELIER Logistics'),('currency','MAD'),('late_threshold','30'),('notifications','true')]: c.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)',(key,val))
            for oid,label,detail in [(1,'Transporteur affecté','Maroc Transit affecté à la commande.'),(1,'Marchandise prise en charge','Départ de Casablanca.'),(5,'Livraison confirmée','Preuve de livraison enregistrée.')]: c.execute('INSERT INTO events(order_id,label,details,created_at) VALUES(?,?,?,?)',(oid,label,detail,now))
            samples=[(1,'Bon de commande','Bon de commande'),(1,'Lettre de voiture CMR','Lettre de voiture / CMR'),(5,'Bon de livraison','Bon de livraison (BL)'),(5,'Preuve de livraison','Preuve de livraison (POD)')]
            for oid,filename,kind in samples:
                stored=f'demo_{oid}_{filename.lower().replace(" ","_")}.txt'
                (UPLOADS/stored).write_text(f'ATELIER — DOCUMENT FICTIF DE DÉMONSTRATION\nType : {kind}\nCommande : {oid}\nCe fichier est un exemple de présentation et ne constitue pas une pièce commerciale réelle.\n',encoding='utf-8')
                c.execute('INSERT INTO documents(order_id,name,kind,filename,uploaded_at) VALUES(?,?,?,?,?)',(oid,filename+'.txt',kind,stored,now))

@app.on_event('startup')
def startup(): init_db()

def dicts(rows): return [dict(r) for r in rows]
def order_query():
    return '''SELECT o.*, COALESCE(c.name,'À désigner') carrier_name FROM orders o LEFT JOIN carriers c ON c.id=o.carrier_id'''

@app.get('/')
def home(): return FileResponse(BASE/'static'/'index.html')
@app.get('/api/health')
def health(): return {'status':'ok','application':'ATELIER TMS','database':'SQLite'}
@app.get('/api/dashboard')
def dashboard():
    with conn() as c:
        total=c.execute('SELECT COUNT(*) FROM orders').fetchone()[0]
        status={r['status']:r['n'] for r in c.execute('SELECT status,COUNT(*) n FROM orders GROUP BY status')}
        active=status.get('En cours',0)+status.get('Planifiée',0)+status.get('À affecter',0)+status.get('Incident',0)
        delivered=status.get('Livrée',0); incidents=c.execute("SELECT COUNT(*) FROM incidents WHERE status='Ouvert'").fetchone()[0]
        punctual=c.execute("SELECT COUNT(*) FROM orders WHERE status='Livrée'").fetchone()[0]
        carrier_count=c.execute('SELECT COUNT(*) FROM carriers WHERE available=1').fetchone()[0]
        revenue=c.execute('SELECT COALESCE(SUM(amount),0) FROM orders').fetchone()[0]
        costs=c.execute('SELECT COALESCE(SUM(c.cost),0) FROM orders o JOIN carriers c ON c.id=o.carrier_id').fetchone()[0]
        margin=revenue-costs
        recent=dicts(c.execute(order_query()+' ORDER BY o.id DESC LIMIT 7').fetchall())
        activity=dicts(c.execute('SELECT e.*,o.ref FROM events e LEFT JOIN orders o ON o.id=e.order_id ORDER BY e.id DESC LIMIT 6').fetchall())
        by_status=[{'label':k,'value':v} for k,v in status.items()]
        monthly=[{'month':m,'orders':n} for m,n in c.execute("SELECT strftime('%m',created_at) month,COUNT(*) n FROM orders GROUP BY month ORDER BY month").fetchall()]
        return {'kpis':{'total_orders':total,'active_orders':active,'to_assign':status.get('À affecter',0),'in_transit':status.get('En cours',0),'planned':status.get('Planifiée',0),'delivered':delivered,'open_incidents':incidents,'active_carriers':carrier_count,'delivery_rate':round(delivered/total*100,1) if total else 0,'revenue':revenue,'carrier_costs':costs,'gross_margin':margin,'margin_rate':round(margin/revenue*100,1) if revenue else 0},'statuses':by_status,'monthly':monthly,'recent':recent,'activity':activity}

@app.get('/api/orders')
def list_orders(q:str='',status:str=''):
    sql=order_query()+' WHERE 1=1'; args=[]
    if q: sql+=' AND (o.ref LIKE ? OR o.client LIKE ? OR o.origin LIKE ? OR o.destination LIKE ?)'; args += [f'%{q}%']*4
    if status: sql+=' AND o.status=?'; args.append(status)
    with conn() as c: return dicts(c.execute(sql+' ORDER BY o.id DESC',args).fetchall())
class OrderIn(BaseModel):
    client:str; origin:str; destination:str; goods:str; vehicle:str='Camion 12T'; pickup_date:str=''; amount:float=0; notes:str=''; ref:str|None=None
@app.post('/api/orders')
def create_order(x:OrderIn):
    now=datetime.now().isoformat(timespec='seconds')
    with conn() as c:
        ref=x.ref or f"TR-{datetime.now():%Y}-{c.execute('SELECT COUNT(*) FROM orders').fetchone()[0]+850:04d}"
        try:
            cur=c.execute("INSERT INTO orders(ref,client,origin,destination,goods,vehicle,pickup_date,amount,notes,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,'À affecter',?,?)",(ref,x.client,x.origin,x.destination,x.goods,x.vehicle,x.pickup_date,x.amount,x.notes,now,now))
        except sqlite3.IntegrityError: raise HTTPException(409,'Cette référence existe déjà.')
        oid=cur.lastrowid; c.execute('INSERT INTO events(order_id,label,details,created_at) VALUES(?,?,?,?)',(oid,'Commande créée','Commande enregistrée et en attente d’affectation.',now))
        return dict(c.execute(order_query()+' WHERE o.id=?',(oid,)).fetchone())
@app.patch('/api/orders/{oid}/status')
def update_status(oid:int,status:str):
    if status not in STATUSES: raise HTTPException(400,'Statut invalide')
    now=datetime.now().isoformat(timespec='seconds')
    with conn() as c:
        if not c.execute('SELECT id FROM orders WHERE id=?',(oid,)).fetchone(): raise HTTPException(404,'Commande introuvable')
        c.execute('UPDATE orders SET status=?,updated_at=? WHERE id=?',(status,now,oid)); c.execute('INSERT INTO events(order_id,label,details,created_at) VALUES(?,?,?,?)',(oid,'Statut modifié',f'Nouveau statut : {status}',now))
        return dict(c.execute(order_query()+' WHERE o.id=?',(oid,)).fetchone())
@app.post('/api/orders/{oid}/assign')
def assign(oid:int, carrier_id:int):
    now=datetime.now().isoformat(timespec='seconds')
    with conn() as c:
        carrier=c.execute('SELECT * FROM carriers WHERE id=? AND available=1',(carrier_id,)).fetchone()
        if not carrier: raise HTTPException(404,'Transporteur indisponible ou introuvable')
        if not c.execute('SELECT id FROM orders WHERE id=?',(oid,)).fetchone(): raise HTTPException(404,'Commande introuvable')
        c.execute("UPDATE orders SET carrier_id=?,status='Planifiée',updated_at=? WHERE id=?",(carrier_id,now,oid))
        c.execute('INSERT INTO events(order_id,label,details,created_at) VALUES(?,?,?,?)',(oid,'Transporteur affecté',f"{carrier['name']} affecté à la commande.",now))
        return dict(c.execute(order_query()+' WHERE o.id=?',(oid,)).fetchone())
@app.get('/api/orders/{oid}/events')
def order_events(oid:int):
    with conn() as c:
        if not c.execute('SELECT id FROM orders WHERE id=?',(oid,)).fetchone(): raise HTTPException(404,'Commande introuvable')
        return dicts(c.execute('SELECT * FROM events WHERE order_id=? ORDER BY id',(oid,)).fetchall())
@app.get('/api/carriers')
def list_carriers():
    with conn() as c: return dicts(c.execute('SELECT * FROM carriers ORDER BY name').fetchall())
class CarrierIn(BaseModel): name:str; zone:str='National'; fleet:int=1; punctuality:float=95; rating:float=4.5; cost:float=0; available:bool=True; phone:str=''; email:str=''
@app.post('/api/carriers')
def add_carrier(x:CarrierIn):
    with conn() as c:
        cur=c.execute('INSERT INTO carriers(name,zone,fleet,punctuality,rating,cost,available,phone,email) VALUES(?,?,?,?,?,?,?,?,?)',(x.name,x.zone,x.fleet,x.punctuality,x.rating,x.cost,int(x.available),x.phone,x.email))
        return dict(c.execute('SELECT * FROM carriers WHERE id=?',(cur.lastrowid,)).fetchone())
@app.patch('/api/carriers/{cid}/availability')
def carrier_availability(cid:int,available:bool):
    with conn() as c:
        cur=c.execute('UPDATE carriers SET available=? WHERE id=?',(int(available),cid))
        if not cur.rowcount: raise HTTPException(404,'Transporteur introuvable')
        return dict(c.execute('SELECT * FROM carriers WHERE id=?',(cid,)).fetchone())
@app.get('/api/tenders')
def list_tenders():
    with conn() as c: return dicts(c.execute('SELECT * FROM tenders ORDER BY id DESC').fetchall())
class TenderIn(BaseModel): shipper:str; origin:str; destination:str; vehicle:str='Camion 12T'; deadline:str=''; offers:int=0; description:str=''
@app.post('/api/tenders')
def add_tender(x:TenderIn):
    with conn() as c:
        ref=f'AO-{datetime.now():%y%m%d}-{c.execute("SELECT COUNT(*) FROM tenders").fetchone()[0]+1:02d}'
        cur=c.execute('INSERT INTO tenders(ref,shipper,origin,destination,vehicle,deadline,offers,status,description,created_at) VALUES(?,?,?,?,?,?,?,\'Ouvert\',?,?)',(ref,x.shipper,x.origin,x.destination,x.vehicle,x.deadline,x.offers,x.description,datetime.now().isoformat(timespec='seconds')))
        return dict(c.execute('SELECT * FROM tenders WHERE id=?',(cur.lastrowid,)).fetchone())
@app.patch('/api/tenders/{tid}/status')
def tender_status(tid:int,status:str):
    if status not in {'Ouvert','Consultation','À comparer','Attribué','Clôturé'}: raise HTTPException(400,'Statut invalide')
    with conn() as c:
        if not c.execute('UPDATE tenders SET status=? WHERE id=?',(status,tid)).rowcount: raise HTTPException(404,'Appel d’offres introuvable')
        return dict(c.execute('SELECT * FROM tenders WHERE id=?',(tid,)).fetchone())
@app.get('/api/incidents')
def list_incidents():
    with conn() as c: return dicts(c.execute('SELECT i.*,o.ref,o.client FROM incidents i LEFT JOIN orders o ON o.id=i.order_id ORDER BY i.id DESC').fetchall())
class IncidentIn(BaseModel): order_id:int; category:str='Retard'; severity:str='Moyenne'; description:str
@app.post('/api/incidents')
def add_incident(x:IncidentIn):
    now=datetime.now().isoformat(timespec='seconds')
    with conn() as c:
        if not c.execute('SELECT id FROM orders WHERE id=?',(x.order_id,)).fetchone(): raise HTTPException(404,'Commande introuvable')
        cur=c.execute('INSERT INTO incidents(order_id,category,severity,description,status,created_at) VALUES(?,?,?,?,\'Ouvert\',?)',(x.order_id,x.category,x.severity,x.description,now))
        c.execute("UPDATE orders SET status='Incident',updated_at=? WHERE id=?",(now,x.order_id)); c.execute('INSERT INTO events(order_id,label,details,created_at) VALUES(?,?,?,?)',(x.order_id,'Incident déclaré',x.description,now))
        return dict(c.execute('SELECT * FROM incidents WHERE id=?',(cur.lastrowid,)).fetchone())
@app.patch('/api/incidents/{iid}/resolve')
def resolve_incident(iid:int):
    now=datetime.now().isoformat(timespec='seconds')
    with conn() as c:
        row=c.execute('SELECT order_id FROM incidents WHERE id=?',(iid,)).fetchone()
        if not row: raise HTTPException(404,'Incident introuvable')
        c.execute("UPDATE incidents SET status='Résolu',resolved_at=? WHERE id=?",(now,iid))
        open_left=c.execute("SELECT COUNT(*) FROM incidents WHERE order_id=? AND status='Ouvert'",(row['order_id'],)).fetchone()[0]
        if not open_left: c.execute("UPDATE orders SET status='En cours',updated_at=? WHERE id=? AND status='Incident'",(now,row['order_id']))
        return {'ok':True,'status':'Résolu'}
@app.get('/api/documents')
def list_documents():
    with conn() as c: return dicts(c.execute('SELECT d.*,o.ref FROM documents d LEFT JOIN orders o ON o.id=d.order_id ORDER BY d.id DESC').fetchall())
@app.post('/api/documents')
async def upload_document(order_id:int,kind:str,name:str|None=None,file:UploadFile=File(...)):
    safe=Path(file.filename or 'document').name
    if len(safe)>180: raise HTTPException(400,'Nom de fichier trop long')
    stamp=datetime.now().strftime('%Y%m%d%H%M%S%f'); stored=f'{stamp}_{safe}'
    content=await file.read()
    if len(content)>12*1024*1024: raise HTTPException(413,'Fichier limité à 12 Mo')
    (UPLOADS/stored).write_bytes(content)
    with conn() as c:
        if not c.execute('SELECT id FROM orders WHERE id=?',(order_id,)).fetchone(): (UPLOADS/stored).unlink(missing_ok=True); raise HTTPException(404,'Commande introuvable')
        cur=c.execute('INSERT INTO documents(order_id,name,kind,filename,uploaded_at) VALUES(?,?,?,?,?)',(order_id,name or safe,kind,stored,datetime.now().isoformat(timespec='seconds')))
        return dict(c.execute('SELECT d.*,o.ref FROM documents d LEFT JOIN orders o ON o.id=d.order_id WHERE d.id=?',(cur.lastrowid,)).fetchone())
@app.get('/api/documents/{did}/download')
def download_document(did:int):
    with conn() as c: row=c.execute('SELECT * FROM documents WHERE id=?',(did,)).fetchone()
    if not row or not (UPLOADS/row['filename']).exists(): raise HTTPException(404,'Document introuvable')
    return FileResponse(UPLOADS/row['filename'],filename=row['name'])
@app.get('/api/settings')
def get_settings():
    with conn() as c: return {r['key']:r['value'] for r in c.execute('SELECT * FROM settings')}
class SettingsIn(BaseModel): values:dict[str,str]
@app.put('/api/settings')
def save_settings(x:SettingsIn):
    with conn() as c:
        for k,v in x.values.items(): c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(k,str(v)))
    return {'ok':True}
@app.get('/api/export/orders.csv')
def export_orders():
    with conn() as c: rows=dicts(c.execute(order_query()+' ORDER BY o.id DESC').fetchall())
    out=io.StringIO(); fields=['ref','client','origin','destination','goods','vehicle','pickup_date','amount','carrier_name','status']
    w=csv.DictWriter(out,fieldnames=fields); w.writeheader(); w.writerows([{k:r.get(k) for k in fields} for r in rows])
    return StreamingResponse(iter([('\ufeff'+out.getvalue()).encode('utf-8')]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=atelier_commandes.csv'})

app.mount('/uploads',StaticFiles(directory=UPLOADS),name='uploads')
