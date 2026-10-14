import csv
import io
import json
import os
import re
import secrets
import sqlite3
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

from flask import Flask, Response, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from seed_demo import generate

ROOT = Path(__file__).resolve().parent
DEMO_USERNAME = 'demo'
DEMO_PASSWORD = 'Estoque@123'


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.update(DATABASE=str(ROOT/'instance'/'atlas.sqlite3'), DATA_DIR=str(ROOT/'data'),
                      SESSION_COOKIE_NAME='atlas_estoque', SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE='Lax', MAX_CONTENT_LENGTH=1024*1024)
    app.config.update(test_config or {})
    if not app.config.get('SECRET_KEY'):
        secret_path = ROOT/'instance'/'session.key'
        secret_path.parent.mkdir(exist_ok=True)
        if not secret_path.exists():
            with secret_path.open('x', encoding='ascii') as stream:
                stream.write(secrets.token_hex(32))
        app.config['SECRET_KEY'] = secret_path.read_text(encoding='ascii').strip()

    def get_db():
        if 'db' not in g:
            g.db = sqlite3.connect(app.config['DATABASE'])
            g.db.row_factory = sqlite3.Row
            g.db.execute('PRAGMA foreign_keys=ON')
        return g.db

    @app.teardown_appcontext
    def close_db(_error=None):
        database = g.pop('db', None)
        if database is not None:
            database.close()

    def csrf_token():
        if '_csrf' not in session:
            session['_csrf'] = secrets.token_urlsafe(32)
        return session['_csrf']

    def valid_csrf():
        received, expected = request.form.get('csrf_token', ''), session.get('_csrf', '')
        return bool(received and expected and secrets.compare_digest(received, expected))

    app.jinja_env.globals['csrf_token'] = csrf_token

    @app.template_filter('money')
    def money(cents):
        return 'R$ ' + f'{cents/100:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')

    @app.template_filter('number')
    def number(value):
        return f'{value:,}'.replace(',', '.')

    @app.template_filter('shortdate')
    def shortdate(value):
        return datetime.fromisoformat(value).strftime('%d/%m · %H:%M')

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if 'user_id' not in session:
                if request.path.startswith('/api/'):
                    return jsonify(error='Autenticação obrigatória'), 401
                return redirect(url_for('login'))
            return view(*args, **kwargs)
        return wrapped

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/')
    def home():
        return redirect(url_for('dashboard' if 'user_id' in session else 'login'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            if not valid_csrf():
                flash('Sessão expirada. Atualize a página e tente novamente.', 'error')
                return render_template('login.html', demo_username=DEMO_USERNAME, demo_password=DEMO_PASSWORD), 400
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            user = get_db().execute('SELECT * FROM users WHERE username=? COLLATE NOCASE', (username,)).fetchone()
            if user is None or not check_password_hash(user['password_hash'], password):
                flash('Usuário ou senha inválidos.', 'error')
            else:
                session.clear()
                session.update(user_id=user['id'], username=user['username'], name=user['name'])
                csrf_token()
                return redirect(url_for('dashboard'))
        return render_template('login.html', demo_username=DEMO_USERNAME, demo_password=DEMO_PASSWORD)

    @app.route('/cadastro', methods=['GET', 'POST'])
    def cadastro():
        if request.method == 'POST':
            if not valid_csrf():
                flash('Sessão expirada. Atualize a página e tente novamente.', 'error')
                return render_template('cadastro.html'), 400
            name = request.form.get('name', '').strip()
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            confirmation = request.form.get('confirm_password', '')
            error = None
            if not 2 <= len(name) <= 80:
                error = 'Informe um nome entre 2 e 80 caracteres.'
            elif not re.fullmatch(r'[a-zA-Z0-9_.-]{3,40}', username):
                error = 'Use de 3 a 40 letras, números, pontos, traços ou sublinhados no usuário.'
            elif not 8 <= len(password) <= 128:
                error = 'A senha deve ter entre 8 e 128 caracteres.'
            elif password != confirmation:
                error = 'As senhas não coincidem.'
            if error is None:
                try:
                    get_db().execute('INSERT INTO users (name,username,password_hash,created_at) VALUES (?,?,?,?)',
                                     (name, username, generate_password_hash(password), datetime.now(timezone.utc).isoformat()))
                    get_db().commit()
                except sqlite3.IntegrityError:
                    get_db().rollback()
                    error = 'Este usuário já está cadastrado. Escolha outro nome.'
            if error:
                flash(error, 'error')
            else:
                flash('Conta criada. Entre com o usuário e a senha que você escolheu.', 'success')
                return redirect(url_for('login'))
        return render_template('cadastro.html')

    @app.post('/logout')
    @login_required
    def logout():
        if not valid_csrf():
            return 'Token de sessão inválido.', 400
        session.clear()
        return redirect(url_for('login'))

    def dataset():
        db = get_db()
        warehouses = [dict(r) for r in db.execute('SELECT * FROM warehouses ORDER BY id')]
        categories = [r[0] for r in db.execute('SELECT DISTINCT category FROM products ORDER BY category')]
        selected_cd = request.args.get('cd', '')
        selected_category = request.args.get('categoria', '')
        selected_status = request.args.get('status', '')
        search = request.args.get('q', '').strip()[:80]
        clauses, params = [], []
        if selected_cd:
            clauses.append('s.warehouse_id=?')
            params.append(selected_cd)
        if selected_category:
            clauses.append('p.category=?')
            params.append(selected_category)
        if search:
            clauses.append('(p.name LIKE ? ESCAPE "!" OR p.sku LIKE ? ESCAPE "!")')
            literal = search.replace('!', '!!').replace('%', '!%').replace('_', '!_')
            params.extend(['%'+literal+'%']*2)
        if selected_status == 'critico':
            clauses.append('s.quantity<=s.minimum')
        elif selected_status == 'ruptura':
            clauses.append('s.quantity=0')
        elif selected_status == 'normal':
            clauses.append('s.quantity>s.minimum')
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        rows = [dict(r) for r in db.execute('''SELECT s.*,p.name,p.category,p.unit_cost,w.name AS warehouse,
                 p.sku FROM stocks s JOIN products p ON p.sku=s.sku JOIN warehouses w ON w.id=s.warehouse_id'''
                 + where + ' ORDER BY s.quantity=0 DESC,s.quantity<=s.minimum DESC,p.name,w.id', params)]
        ids = {r['id'] for r in rows}
        movements = [dict(r) for r in db.execute('''SELECT m.*,p.name,p.sku,w.name AS warehouse FROM movements m
                     JOIN stocks s ON s.id=m.stock_id JOIN products p ON p.sku=s.sku
                     JOIN warehouses w ON w.id=s.warehouse_id ORDER BY m.occurred_at DESC,m.id DESC''') if r['stock_id'] in ids]
        metadata = json.loads((Path(app.config['DATA_DIR'])/'metadados.json').read_text(encoding='utf-8'))
        ref = date.fromisoformat(metadata['data_referencia'])
        days = []
        for delta in reversed(range(7)):
            day = ref - timedelta(days=delta)
            items = [m for m in movements if m['occurred_at'][:10] == day.isoformat()]
            days.append(dict(label=day.strftime('%d/%m'),
                             incoming=sum(m['quantity'] for m in items if m['kind']=='entrada'),
                             outgoing=-sum(m['quantity'] for m in items if m['kind']=='saida')))
        maximum = max([d[k] for d in days for k in ('incoming','outgoing')] + [1])
        for day in days:
            day['in_height'] = round(day['incoming']/maximum*130, 1)
            day['out_height'] = round(day['outgoing']/maximum*130, 1)
        grouped = {}
        for row in rows:
            grouped[row['category']] = grouped.get(row['category'], 0) + row['quantity']*row['unit_cost']
            row['status'] = 'ruptura' if row['quantity']==0 else 'critico' if row['quantity']<=row['minimum'] else 'normal'
        composition = [dict(name=k, value=v, percent=round(v/max(sum(grouped.values()),1)*100, 1))
                       for k, v in sorted(grouped.items(), key=lambda item:-item[1])]
        kpis = dict(positions=len(rows), products=len({r['sku'] for r in rows}),
                    units=sum(r['quantity'] for r in rows), value=sum(r['quantity']*r['unit_cost'] for r in rows),
                    critical=sum(r['quantity']<=r['minimum'] for r in rows),
                    stockouts=sum(r['quantity']==0 for r in rows),
                    outgoing=sum(d['outgoing'] for d in days), incoming=sum(d['incoming'] for d in days))
        return dict(rows=rows, movements=movements, warehouses=warehouses, categories=categories,
                    filters=dict(cd=selected_cd,categoria=selected_category,status=selected_status,q=search),
                    kpis=kpis, days=days, composition=composition, reference=ref.strftime('%d/%m/%Y'),
                    metadata=metadata)

    @app.get('/dashboard')
    @login_required
    def dashboard():
        data = dataset()
        page = max(1, request.args.get('pagina', 1, type=int) or 1)
        total_pages = max(1, (len(data['rows'])+17)//18)
        page = min(page, total_pages)
        data['visible_rows'] = data['rows'][(page-1)*18:page*18]
        data.update(page=page,total_pages=total_pages,
                    previous_url=url_for('dashboard', **dict(request.args.to_dict(),pagina=page-1)),
                    next_url=url_for('dashboard', **dict(request.args.to_dict(),pagina=page+1)))
        return render_template('dashboard.html', **data)

    @app.get('/api/resumo')
    @login_required
    def summary():
        data = dataset()
        return jsonify(synthetic=True, kpis=data['kpis'], days=data['days'], reference=data['metadata']['data_referencia'])

    @app.get('/exportar.csv')
    @login_required
    def export_csv():
        rows = dataset()['rows']
        buffer = io.StringIO(newline='')
        writer = csv.writer(buffer, delimiter=';')
        writer.writerow(['sku','produto','categoria','centro','quantidade','estoque_minimo','custo_unitario_brl','valor_total_brl','status','dados_ficticios'])
        for row in rows:
            # Prevent spreadsheet formula interpretation in exported text.
            safe = lambda text: "'"+text if text.startswith(('=','+','-','@')) else text
            writer.writerow([row['sku'],safe(row['name']),safe(row['category']),safe(row['warehouse']),
                             row['quantity'],row['minimum'],f"{row['unit_cost']/100:.2f}",
                             f"{row['quantity']*row['unit_cost']/100:.2f}",row['status'],'sim'])
        return Response('\ufeff'+buffer.getvalue(), mimetype='text/csv; charset=utf-8',
                        headers={'Content-Disposition':'attachment; filename=atlas_estoque_ficticio.csv'})

    @app.get('/saude')
    def health():
        return jsonify(status='ok', synthetic=True)

    with app.app_context():
        Path(app.config['DATABASE']).parent.mkdir(parents=True, exist_ok=True)
        data_dir = Path(app.config['DATA_DIR'])
        if not (data_dir/'metadados.json').exists():
            generate(data_dir)
        db = get_db()
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,password_hash TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS warehouses(id INTEGER PRIMARY KEY,name TEXT NOT NULL,city TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS products(sku TEXT PRIMARY KEY,name TEXT NOT NULL,category TEXT NOT NULL,unit_cost INTEGER NOT NULL CHECK(unit_cost>=0));
        CREATE TABLE IF NOT EXISTS stocks(id INTEGER PRIMARY KEY,sku TEXT NOT NULL REFERENCES products(sku),
            warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),opening_quantity INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity>=0),minimum INTEGER NOT NULL,maximum INTEGER NOT NULL,UNIQUE(sku,warehouse_id));
        CREATE TABLE IF NOT EXISTS movements(id INTEGER PRIMARY KEY,stock_id INTEGER NOT NULL REFERENCES stocks(id),
            kind TEXT NOT NULL CHECK(kind IN ('entrada','saida','ajuste')),quantity INTEGER NOT NULL,occurred_at TEXT NOT NULL,document TEXT NOT NULL);
        ''')
        if db.execute('SELECT count(*) FROM stocks').fetchone()[0] == 0:
            def load(name):
                with (data_dir/name).open(encoding='utf-8-sig', newline='') as stream:
                    return list(csv.DictReader(stream))
            db.executemany('INSERT INTO warehouses VALUES (?,?,?)', [(r['id'],r['nome'],r['cidade']) for r in load('centros_ficticios.csv')])
            db.executemany('INSERT INTO products VALUES (?,?,?,?)', [(r['sku'],r['nome'],r['categoria'],r['custo_unitario_centavos']) for r in load('produtos_ficticios.csv')])
            db.executemany('INSERT INTO stocks VALUES (?,?,?,?,?,?,?)', [(r['id'],r['sku'],r['cd_id'],r['saldo_inicial'],r['quantidade'],r['estoque_minimo'],r['estoque_maximo']) for r in load('estoque_ficticio.csv')])
            db.executemany('INSERT INTO movements VALUES (?,?,?,?,?,?)', [(r['id'],r['estoque_id'],r['tipo'],r['quantidade'],r['data_hora'],r['documento']) for r in load('movimentacoes_ficticias.csv')])
        if db.execute('SELECT id FROM users WHERE username=?', (DEMO_USERNAME,)).fetchone() is None:
            db.execute('INSERT INTO users(name,username,password_hash,created_at) VALUES (?,?,?,?)',
                       ('Conta demonstração',DEMO_USERNAME,generate_password_hash(DEMO_PASSWORD),datetime.now(timezone.utc).isoformat()))
        db.commit()
    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', 5052)), debug=False)
