from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.utils import secure_filename
from functools import wraps
from pathlib import Path
import sqlite3, os, json, uuid, mimetypes

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'atelier.db'
UPLOAD_DIR = BASE_DIR / 'static' / 'uploads'
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get('ATELIER_SECRET_KEY', 'atelier-v4-1-local')
ADMIN_USER = os.environ.get('ATELIER_ADMIN_USER', 'admin')
ADMIN_PASSWORD = os.environ.get('ATELIER_ADMIN_PASSWORD', 'Atelier2026!')

SUPABASE_URL = os.environ.get('SUPABASE_URL', '').strip()
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '').strip()
SUPABASE_BUCKET = os.environ.get('SUPABASE_BUCKET', 'product-images').strip()
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)
sb = None
if USE_SUPABASE:
    from supabase import create_client
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = get_db()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS products (
      id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
      subtitle TEXT DEFAULT '', description TEXT DEFAULT '', price INTEGER NOT NULL,
      category TEXT NOT NULL DEFAULT 'Ropa', sizes TEXT DEFAULT '[]', colors TEXT DEFAULT '[]',
      image TEXT DEFAULT '', active INTEGER DEFAULT 1, featured INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS product_images (
      id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, image TEXT NOT NULL,
      color TEXT DEFAULT '', sort_order INTEGER DEFAULT 0, is_primary INTEGER DEFAULT 0
    );''')
    for p in c.execute('SELECT id,image FROM products').fetchall():
        n = c.execute('SELECT COUNT(*) c FROM product_images WHERE product_id=?',(p['id'],)).fetchone()['c']
        if n == 0 and p['image']:
            c.execute('INSERT INTO product_images(product_id,image,color,sort_order,is_primary) VALUES(?,?,?,?,1)',(p['id'],p['image'],'',0))
    c.commit(); c.close()

def split_csv(v): return [x.strip() for x in (v or '').split(',') if x.strip()]
def parse_list(v):
    if isinstance(v,list): return v
    try: return json.loads(v or '[]')
    except: return []

def local_product(c,row):
    imgs=[dict(x) for x in c.execute('SELECT id,image,color,sort_order,is_primary FROM product_images WHERE product_id=? ORDER BY is_primary DESC,sort_order,id',(row['id'],)).fetchall()]
    main=imgs[0]['image'] if imgs else row['image']
    return {'id':row['id'],'ref':row['ref'],'name':row['name'],'subtitle':row['subtitle'],'description':row['description'],'price':row['price'],'category':row['category'],'sizes':parse_list(row['sizes']),'colors':parse_list(row['colors']),'image':main,'gallery':imgs,'active':bool(row['active']),'featured':bool(row['featured'])}

def remote_products(active_only=False):
    q=sb.table('products').select('*')
    if active_only: q=q.eq('active',True)
    ps=q.order('featured',desc=True).order('id',desc=True).execute().data or []
    imgs=sb.table('product_images').select('*').order('sort_order').execute().data or []
    by={}
    for i in imgs: by.setdefault(i['product_id'],[]).append(i)
    out=[]
    for p in ps:
        g=sorted(by.get(p['id'],[]),key=lambda x:(not bool(x.get('is_primary')),x.get('sort_order',0),x.get('id',0)))
        out.append({'id':p['id'],'ref':p['ref'],'name':p['name'],'subtitle':p.get('subtitle',''),'description':p.get('description',''),'price':p['price'],'category':p.get('category','Ropa'),'sizes':p.get('sizes') or [],'colors':p.get('colors') or [],'image':g[0]['image'] if g else p.get('image',''),'gallery':g,'active':bool(p.get('active',True)),'featured':bool(p.get('featured',True))})
    return out

def all_products(active_only=False):
    if USE_SUPABASE: return remote_products(active_only)
    c=get_db(); sql='SELECT * FROM products'+(' WHERE active=1' if active_only else '')+' ORDER BY featured DESC,id DESC'
    out=[local_product(c,r) for r in c.execute(sql).fetchall()]; c.close(); return out

def login_required(fn):
    @wraps(fn)
    def w(*a,**k):
        if not session.get('admin'): return redirect(url_for('admin_login'))
        return fn(*a,**k)
    return w

def save_local_file(f):
    ext=Path(secure_filename(f.filename)).suffix.lower()
    if ext not in ['.jpg','.jpeg','.png','.webp']: raise ValueError('Formato de imagen no permitido.')
    name=f'{uuid.uuid4().hex[:14]}{ext}'; f.save(UPLOAD_DIR/name); return f'uploads/{name}'

def upload_remote(f,ref):
    ext=Path(secure_filename(f.filename)).suffix.lower()
    if ext not in ['.jpg','.jpeg','.png','.webp']: raise ValueError('Formato de imagen no permitido.')
    safe=''.join(ch for ch in ref if ch.isalnum() or ch in '-_') or 'producto'
    path=f'{safe}/{uuid.uuid4().hex[:14]}{ext}'
    content=f.read(); mime=mimetypes.guess_type(f.filename)[0] or 'application/octet-stream'
    sb.storage.from_(SUPABASE_BUCKET).upload(path=path,file=content,file_options={'content-type':mime,'upsert':'false'})
    return sb.storage.from_(SUPABASE_BUCKET).get_public_url(path), path

def upload_local_to_remote(rel,ref):
    full=BASE_DIR/'static'/rel
    if not full.exists(): return rel,''
    safe=''.join(ch for ch in ref if ch.isalnum() or ch in '-_') or 'producto'
    path=f'{safe}/{uuid.uuid4().hex[:14]}{full.suffix.lower()}'
    mime=mimetypes.guess_type(full.name)[0] or 'application/octet-stream'
    sb.storage.from_(SUPABASE_BUCKET).upload(path=path,file=full.read_bytes(),file_options={'content-type':mime,'upsert':'false'})
    return sb.storage.from_(SUPABASE_BUCKET).get_public_url(path),path

@app.route('/')
def shop(): return render_template('shop.html')

@app.route('/api/products')
def api_products(): return jsonify(all_products(True))

@app.route('/health')
def health(): return jsonify({'ok':True,'storage':'supabase' if USE_SUPABASE else 'sqlite-local','supabase_configured':USE_SUPABASE})

@app.route('/admin/login',methods=['GET','POST'])
def admin_login():
    if request.method=='POST':
        if request.form.get('username')==ADMIN_USER and request.form.get('password')==ADMIN_PASSWORD:
            session['admin']=True; return redirect(url_for('admin'))
        flash('Usuario o contraseña incorrectos.')
    return render_template('login.html')

@app.route('/admin/logout')
def admin_logout(): session.clear(); return redirect(url_for('admin_login'))

@app.route('/admin')
@login_required
def admin():
    return render_template('admin.html',products=all_products(False),storage_mode='Supabase permanente' if USE_SUPABASE else 'SQLite local / temporal en Render',supabase_ready=USE_SUPABASE,draft=session.get('draft_product',{}))

@app.route('/admin/product/new',methods=['POST'])
@login_required
def admin_new(): return save_product(None)

@app.route('/admin/product/<int:pid>',methods=['POST'])
@login_required
def admin_update(pid): return save_product(pid)

def save_product(pid):
    f=request.form
    ref=f.get('ref','').strip()
    name=f.get('name','').strip()
    subtitle=f.get('subtitle','').strip()
    desc=f.get('description','').strip()
    category=f.get('category','Ropa').strip() or 'Ropa'
    raw_price=(f.get('price','0') or '0').replace('.','').replace(',','').strip()
    sizes=split_csv(f.get('sizes'))
    colors=split_csv(f.get('colors'))
    active=f.get('active')=='on'
    featured=f.get('featured')=='on'

    errors=[]
    if not ref: errors.append('La referencia es obligatoria.')
    if not name: errors.append('El nombre es obligatorio.')
    if not raw_price.isdigit() or int(raw_price) <= 0: errors.append('El precio debe ser un número mayor que 0.')
    if errors:
        session['draft_product']={
            'ref':ref,'name':name,'subtitle':subtitle,'description':desc,'price':raw_price,
            'category':category,'sizes':f.get('sizes',''),'colors':f.get('colors',''),
            'cover_color':f.get('cover_color',''),'gallery_colors':f.get('gallery_colors',''),
            'active':active,'featured':featured
        }
        for msg in errors: flash(msg,'error')
        return redirect(url_for('admin'))

    price=int(raw_price)
    payload={'ref':ref,'name':name,'subtitle':subtitle,'description':desc,'price':price,
             'category':category,'sizes':sizes,'colors':colors,'active':active,'featured':featured}

    if USE_SUPABASE:
        try:
            if pid is None:
                resp=sb.table('products').insert(payload).execute()
                data=resp.data or []
                if not data:
                    raise RuntimeError('Supabase no devolvió el producto creado.')
                pid=data[0]['id']
            else:
                resp=sb.table('products').update(payload).eq('id',pid).execute()
                if resp.data is None:
                    raise RuntimeError('Supabase no confirmó la actualización.')

            cover=request.files.get('cover_image')
            if cover and cover.filename:
                url,path=upload_remote(cover,ref)
                sb.table('product_images').update({'is_primary':False}).eq('product_id',pid).execute()
                img_resp=sb.table('product_images').insert({
                    'product_id':pid,'image':url,'storage_path':path,
                    'color':f.get('cover_color','').strip(),'sort_order':-1,'is_primary':True
                }).execute()
                if not (img_resp.data or []):
                    raise RuntimeError('El producto se guardó, pero la portada no pudo registrarse.')
                sb.table('products').update({'image':url}).eq('id',pid).execute()

            gs=[x for x in request.files.getlist('gallery_images') if x and x.filename]
            gc=split_csv(f.get('gallery_colors'))
            existing=sb.table('product_images').select('sort_order').eq('product_id',pid).execute().data or []
            mx=max([x.get('sort_order',0) for x in existing] or [0])
            for i,g in enumerate(gs):
                url,path=upload_remote(g,ref)
                img_resp=sb.table('product_images').insert({
                    'product_id':pid,'image':url,'storage_path':path,
                    'color':gc[i] if i<len(gc) else '','sort_order':mx+i+1,'is_primary':False
                }).execute()
                if not (img_resp.data or []):
                    raise RuntimeError(f'No se pudo registrar la imagen adicional #{i+1}.')

            for rid in request.form.getlist('remove_image'):
                rows=sb.table('product_images').select('*').eq('id',int(rid)).eq('product_id',pid).execute().data or []
                if rows:
                    if rows[0].get('storage_path'):
                        try: sb.storage.from_(SUPABASE_BUCKET).remove([rows[0]['storage_path']])
                        except Exception: pass
                    sb.table('product_images').delete().eq('id',int(rid)).execute()

            rem=sb.table('product_images').select('*').eq('product_id',pid).order('is_primary',desc=True).order('sort_order').execute().data or []
            if rem:
                if not any(bool(x.get('is_primary')) for x in rem):
                    sb.table('product_images').update({'is_primary':True}).eq('id',rem[0]['id']).execute()
                    rem[0]['is_primary']=True
                primary=sorted(rem,key=lambda x:(not bool(x.get('is_primary')),x.get('sort_order',0),x.get('id',0)))[0]
                sb.table('products').update({'image':primary['image']}).eq('id',pid).execute()
            else:
                sb.table('products').update({'image':''}).eq('id',pid).execute()

            session.pop('draft_product',None)
            flash('✅ Producto publicado correctamente en Supabase.','success')
            return redirect(url_for('admin'))

        except Exception as e:
            session['draft_product']={
                'ref':ref,'name':name,'subtitle':subtitle,'description':desc,'price':raw_price,
                'category':category,'sizes':f.get('sizes',''),'colors':f.get('colors',''),
                'cover_color':f.get('cover_color',''),'gallery_colors':f.get('gallery_colors',''),
                'active':active,'featured':featured
            }
            app.logger.exception('Error guardando producto en Supabase')
            flash(f'❌ No se pudo publicar el producto: {e}','error')
            return redirect(url_for('admin'))

    c=get_db()
    try:
        if pid is None:
            cur=c.execute('INSERT INTO products(ref,name,subtitle,description,price,category,sizes,colors,image,active,featured) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                          (ref,name,subtitle,desc,price,category,json.dumps(sizes,ensure_ascii=False),
                           json.dumps(colors,ensure_ascii=False),'',int(active),int(featured)))
            pid=cur.lastrowid
        else:
            c.execute('UPDATE products SET ref=?,name=?,subtitle=?,description=?,price=?,category=?,sizes=?,colors=?,active=?,featured=? WHERE id=?',
                      (ref,name,subtitle,desc,price,category,json.dumps(sizes,ensure_ascii=False),
                       json.dumps(colors,ensure_ascii=False),int(active),int(featured),pid))

        cover=request.files.get('cover_image')
        if cover and cover.filename:
            path=save_local_file(cover)
            c.execute('UPDATE product_images SET is_primary=0 WHERE product_id=?',(pid,))
            c.execute('INSERT INTO product_images(product_id,image,color,sort_order,is_primary) VALUES(?,?,?,?,1)',
                      (pid,path,f.get('cover_color','').strip(),-1))
            c.execute('UPDATE products SET image=? WHERE id=?',(path,pid))

        gs=[x for x in request.files.getlist('gallery_images') if x and x.filename]
        gc=split_csv(f.get('gallery_colors'))
        mx=c.execute('SELECT COALESCE(MAX(sort_order),0) m FROM product_images WHERE product_id=?',(pid,)).fetchone()['m']
        for i,g in enumerate(gs):
            c.execute('INSERT INTO product_images(product_id,image,color,sort_order,is_primary) VALUES(?,?,?,?,0)',
                      (pid,save_local_file(g),gc[i] if i<len(gc) else '',mx+i+1))

        for rid in request.form.getlist('remove_image'):
            c.execute('DELETE FROM product_images WHERE id=? AND product_id=?',(int(rid),pid))

        imgs=c.execute('SELECT * FROM product_images WHERE product_id=? ORDER BY is_primary DESC,sort_order,id',(pid,)).fetchall()
        if imgs:
            if not any(x['is_primary'] for x in imgs):
                c.execute('UPDATE product_images SET is_primary=1 WHERE id=?',(imgs[0]['id'],))
            first=c.execute('SELECT image FROM product_images WHERE product_id=? ORDER BY is_primary DESC,sort_order,id LIMIT 1',(pid,)).fetchone()
            c.execute('UPDATE products SET image=? WHERE id=?',(first['image'],pid))
        else:
            c.execute("UPDATE products SET image='' WHERE id=?",(pid,))
        c.commit()
        session.pop('draft_product',None)
        flash('✅ Producto guardado localmente.','success')
    except Exception as e:
        c.rollback()
        session['draft_product']={
            'ref':ref,'name':name,'subtitle':subtitle,'description':desc,'price':raw_price,
            'category':category,'sizes':f.get('sizes',''),'colors':f.get('colors',''),
            'cover_color':f.get('cover_color',''),'gallery_colors':f.get('gallery_colors',''),
            'active':active,'featured':featured
        }
        flash(f'❌ No se pudo guardar: {e}','error')
    finally:
        c.close()
    return redirect(url_for('admin'))

@app.route('/admin/product/<int:pid>/delete',methods=['POST'])
@login_required
def admin_delete(pid):
    if USE_SUPABASE:
        imgs=sb.table('product_images').select('*').eq('product_id',pid).execute().data or []
        for img in imgs:
            if img.get('storage_path'):
                try: sb.storage.from_(SUPABASE_BUCKET).remove([img['storage_path']])
                except: pass
        sb.table('product_images').delete().eq('product_id',pid).execute(); sb.table('products').delete().eq('id',pid).execute(); flash('Producto eliminado.'); return redirect(url_for('admin'))
    c=get_db(); c.execute('DELETE FROM product_images WHERE product_id=?',(pid,)); c.execute('DELETE FROM products WHERE id=?',(pid,)); c.commit(); c.close(); flash('Producto eliminado.'); return redirect(url_for('admin'))

@app.route('/admin/migrate-local-to-supabase',methods=['POST'])
@login_required
def migrate_local_to_supabase():
    if not USE_SUPABASE: flash('Primero configura Supabase en Render.'); return redirect(url_for('admin'))
    c=get_db(); np=ni=0
    try:
        for p in c.execute('SELECT * FROM products ORDER BY id').fetchall():
            payload={'ref':p['ref'],'name':p['name'],'subtitle':p['subtitle'],'description':p['description'],'price':p['price'],'category':p['category'],'sizes':parse_list(p['sizes']),'colors':parse_list(p['colors']),'active':bool(p['active']),'featured':bool(p['featured']),'image':''}
            ex=sb.table('products').select('*').eq('ref',p['ref']).execute().data or []
            remote=(sb.table('products').update(payload).eq('ref',p['ref']).execute().data[0] if ex else sb.table('products').insert(payload).execute().data[0]); rid=remote['id']; np+=1
            if sb.table('product_images').select('id').eq('product_id',rid).execute().data: continue
            first=''
            for img in c.execute('SELECT * FROM product_images WHERE product_id=? ORDER BY is_primary DESC,sort_order,id',(p['id'],)).fetchall():
                if str(img['image']).startswith('http'): url,path=img['image'],''
                else: url,path=upload_local_to_remote(img['image'],p['ref'])
                sb.table('product_images').insert({'product_id':rid,'image':url,'storage_path':path,'color':img['color'],'sort_order':img['sort_order'],'is_primary':bool(img['is_primary'])}).execute(); ni+=1
                if not first or img['is_primary']: first=url
            if first: sb.table('products').update({'image':first}).eq('id',rid).execute()
        flash(f'Migración terminada: {np} productos y {ni} imágenes.')
    except Exception as e: flash(f'Error durante la migración: {e}')
    finally: c.close()
    return redirect(url_for('admin'))

if __name__=='__main__':
    init_db(); app.run(host='0.0.0.0',port=int(os.environ.get('PORT','5000')),debug=True)
