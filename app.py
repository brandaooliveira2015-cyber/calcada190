from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash
from flask_cors import CORS
from database import db
from models import Produto, Pedido, Despesa, Rider, Evento
from datetime import datetime, date, timedelta
from werkzeug.utils import secure_filename
import requests
import os

app = Flask(__name__)
CORS(app)

# ==========================
# CONFIGURAÇÕES
# ==========================

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "calcada190-secret-2025"
)

# PostgreSQL no Render / SQLite local caso DATABASE_URL não exista
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///calcada190.db"
)

# Compatibilidade Render
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://",
        "postgresql://",
        1
    )

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# ==========================
# UPLOADS
# ==========================

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

# ==========================
# VARIÁVEIS DE AMBIENTE
# ==========================

CIELO_CLIENT_ID    = os.environ.get('CIELO_CLIENT_ID', '')
CIELO_ACCESS_TOKEN = os.environ.get('CIELO_ACCESS_TOKEN', '')
CIELO_MERCHANT_ID  = os.environ.get('CIELO_MERCHANT_ID', '')

TZ_OFFSET      = int(os.environ.get('TZ_OFFSET_HOURS', '-4'))
APP_SYNC_TOKEN = os.environ.get('APP_SYNC_TOKEN', 'calcada190-app-token')

# ==========================
# INICIALIZA BANCO
# ==========================

db.init_app(app)

with app.app_context():
    db.create_all()

# ==========================
# TESTE
# ==========================

print("=" * 50)
print("BANCO:", DATABASE_URL)
print("=" * 50)


with app.app_context():
    db.create_all()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logado'):
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated


def dono_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logado'):
            return redirect(url_for('login_page'))
        if session.get('perfil') != 'dono':
            return jsonify({'erro': 'Acesso restrito ao dono'}), 403
        return f(*args, **kwargs)
    return decorated


def app_auth_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        auth  = request.headers.get('Authorization', '')
        token = auth.replace('Bearer ', '').strip()
        if token != APP_SYNC_TOKEN:
            return jsonify({'erro': 'Token inválido'}), 401
        return f(*args, **kwargs)
    return decorated


def get_hoje_utc():
    agora_utc    = datetime.utcnow()
    agora_local  = agora_utc + timedelta(hours=TZ_OFFSET)
    inicio_local = agora_local.replace(hour=0,  minute=0,  second=0,  microsecond=0)
    fim_local    = agora_local.replace(hour=23, minute=59, second=59, microsecond=999999)
    return inicio_local - timedelta(hours=TZ_OFFSET), fim_local - timedelta(hours=TZ_OFFSET)


def get_periodo_datas(periodo):
    agora_utc   = datetime.utcnow()
    agora_local = agora_utc + timedelta(hours=TZ_OFFSET)
    hoje_local  = agora_local.date()
    if periodo == 'semana':
        inicio_local = hoje_local - timedelta(days=hoje_local.weekday())
    elif periodo == 'mes':
        inicio_local = hoje_local.replace(day=1)
    else:
        inicio_local = hoje_local
    inicio_dt = datetime.combine(inicio_local, datetime.min.time())
    fim_dt    = datetime.combine(hoje_local,   datetime.max.time())
    return inicio_dt - timedelta(hours=TZ_OFFSET), fim_dt - timedelta(hours=TZ_OFFSET)


def hora_local(dt_utc):
    if not dt_utc:
        return '—'
    return (dt_utc + timedelta(hours=TZ_OFFSET)).strftime('%H:%M')


def produto_dict(p):
    return {
        'id':             p.id,
        'nome':           p.nome,
        'preco_venda':    p.preco_venda,
        'preco_custo':    p.preco_custo,
        'categoria':      p.categoria,
        'estoque':        p.estoque,
        'estoque_minimo': p.estoque_minimo,
        'disponivel':     p.disponivel if p.disponivel is not None else True,
        'foto':           f'/static/uploads/{p.foto}' if p.foto else None,
        'atualizado_em':  p.criado_em.isoformat() if p.criado_em else None,
    }


# ============================================================
# AUTH — Login Fixo
# ============================================================

LOGIN_SISTEMA = "calcada190ml."
SENHA_SISTEMA = "calcada190ml."

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if session.get('logado'):
        return redirect(url_for('dashboard_page'))

    erro = None

    if request.method == 'POST':
        login = request.form.get('login', '').strip()
        senha = request.form.get('senha', '').strip()

        if login == LOGIN_SISTEMA and senha == SENHA_SISTEMA:
            session['logado'] = True
            session['login'] = LOGIN_SISTEMA
            session['nome'] = 'Administrador'
            session['perfil'] = 'dono'

            return redirect(url_for('dashboard_page'))

        erro = 'Login ou senha incorretos.'

    return render_template('login.html', erro=erro)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))


# ============================================================
# PÁGINAS DO SISTEMA
# ============================================================

@app.route('/')
@login_required
def index():
    return redirect(url_for('dashboard_page'))

@app.route('/dashboard')
@login_required
def dashboard_page():
    return render_template('dashboard.html',
        usuario=session.get('nome'), perfil=session.get('perfil'))

@app.route('/pdv')
@login_required
def pdv_page():
    return render_template('pdv.html',
        usuario=session.get('nome'), perfil=session.get('perfil'))

@app.route('/produtos')
@login_required
def produtos_page():
    return render_template('produtos.html',
        usuario=session.get('nome'), perfil=session.get('perfil'))

@app.route('/despesas')
@login_required
def despesas_page():
    return render_template('despesas.html',
        usuario=session.get('nome'), perfil=session.get('perfil'))

@app.route('/pedidos')
@login_required
def pedidos_page():
    return render_template('pedidos.html',
        usuario=session.get('nome'), perfil=session.get('perfil'))

@app.route('/faturamento')
@login_required
def faturamento_page():
    return render_template('faturamento.html',
        usuario=session.get('nome'), perfil=session.get('perfil'))

@app.route('/funcionarios')
@login_required
def funcionarios_page():
    return render_template('funcionarios.html',
        usuario=session.get('nome'), perfil=session.get('perfil'))

@app.route('/usuarios')
@login_required
def usuarios_page():
    if session.get('perfil') != 'dono':
        return redirect(url_for('dashboard_page'))
    return render_template('usuarios.html',
        usuario=session.get('nome'), perfil=session.get('perfil'))


# ============================================================
# API USUÁRIOS (só dono)
# ============================================================

@app.route('/api/usuarios', methods=['GET'])
@dono_required
def listar_usuarios():
    users = Usuario.query.order_by(Usuario.criado_em.desc()).all()
    return jsonify([{
        'id': u.id, 'nome': u.nome, 'email': u.email,
        'login': u.login, 'perfil': u.perfil, 'ativo': u.ativo,
        'criado_em': u.criado_em.strftime('%d/%m/%Y') if u.criado_em else ''
    } for u in users])

@app.route('/api/usuarios/<int:uid>/toggle', methods=['POST'])
@dono_required
def toggle_usuario(uid):
    u = Usuario.query.get_or_404(uid)
    if u.login == 'calcada190':
        return jsonify({'erro': 'Não é possível desativar o admin principal'}), 400
    u.ativo = not u.ativo
    db.session.commit()
    return jsonify({'ok': True, 'ativo': u.ativo})

@app.route('/api/usuarios/<int:uid>/perfil', methods=['POST'])
@dono_required
def alterar_perfil(uid):
    u = Usuario.query.get_or_404(uid)
    perfil = request.json.get('perfil')
    if perfil not in ('dono', 'gerente', 'operador'):
        return jsonify({'erro': 'Perfil inválido'}), 400
    u.perfil = perfil
    db.session.commit()
    return jsonify({'ok': True})

@app.route('/api/usuarios/<int:uid>', methods=['DELETE'])
@dono_required
def excluir_usuario(uid):
    u = Usuario.query.get_or_404(uid)
    if u.login == 'calcada190':
        return jsonify({'erro': 'Não é possível excluir o admin principal'}), 400
    db.session.delete(u)
    db.session.commit()
    return jsonify({'ok': True})


# ============================================================
# API PRODUTOS
# ============================================================

@app.route('/api/produtos', methods=['GET'])
@login_required
def listar_produtos():
    prods = Produto.query.filter_by(ativo=True).order_by(Produto.nome).all()
    return jsonify([produto_dict(p) for p in prods])

@app.route('/api/produtos', methods=['POST'])
@login_required
def criar_produto():
    nome           = request.form.get('nome', '').upper().strip()
    preco_venda    = float(request.form.get('preco_venda', 0))
    preco_custo    = float(request.form.get('preco_custo', 0))
    categoria      = request.form.get('categoria', 'Outro')
    estoque        = int(request.form.get('estoque', 0))
    estoque_minimo = int(request.form.get('estoque_minimo', 0))
    foto_nome = None
    if 'foto' in request.files:
        f = request.files['foto']
        if f and f.filename and allowed_file(f.filename):
            fn = secure_filename(f.filename)
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
            foto_nome = fn
    p = Produto(nome=nome, preco_venda=preco_venda, preco_custo=preco_custo,
                categoria=categoria, estoque=estoque, estoque_minimo=estoque_minimo,
                foto=foto_nome, disponivel=True)
    db.session.add(p)
    db.session.commit()
    return jsonify({'ok': True, 'id': p.id}), 201

@app.route('/api/produtos/<int:pid>', methods=['PUT'])
@login_required
def editar_produto(pid):
    p = Produto.query.get_or_404(pid)
    p.nome           = request.form.get('nome', p.nome).upper().strip()
    p.preco_venda    = float(request.form.get('preco_venda', p.preco_venda))
    p.preco_custo    = float(request.form.get('preco_custo', p.preco_custo))
    p.categoria      = request.form.get('categoria', p.categoria)
    p.estoque        = int(request.form.get('estoque', p.estoque))
    p.estoque_minimo = int(request.form.get('estoque_minimo', p.estoque_minimo))
    if 'foto' in request.files:
        f = request.files['foto']
        if f and f.filename and allowed_file(f.filename):
            fn = secure_filename(f.filename)
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
            p.foto = fn
    db.session.commit()
    return jsonify({'ok': True})

@app.route('/api/produtos/<int:pid>', methods=['DELETE'])
@login_required
def excluir_produto(pid):
    p = Produto.query.get_or_404(pid)
    p.ativo = False
    db.session.commit()
    return jsonify({'ok': True})

@app.route('/api/produtos/<int:pid>/toggle', methods=['POST'])
@login_required
def toggle_disponibilidade(pid):
    p = Produto.query.get_or_404(pid)
    p.disponivel = not (p.disponivel if p.disponivel is not None else True)
    db.session.commit()
    return jsonify({'ok': True, 'disponivel': p.disponivel})


# ============================================================
# API PEDIDOS
# ============================================================

@app.route('/api/pedidos', methods=['GET'])
@login_required
def listar_pedidos():
    origem         = request.args.get('origem')
    forma          = request.args.get('forma')
    periodo        = request.args.get('periodo', 'hoje')
    data_especifica = request.args.get('data')   # ex: 2026-06-06
    mes_especifico  = request.args.get('mes')    # ex: 2026-06
    limit          = request.args.get('limit', type=int)

    # ── Define intervalo ────────────────────────────────────
    if data_especifica:
        # Um dia específico em horário local (MS = UTC-4)
        from datetime import datetime, timedelta, timezone
        tz_offset = timedelta(hours=-4)
        tz_local  = timezone(tz_offset)
        d = datetime.strptime(data_especifica, '%Y-%m-%d')
        inicio = datetime(d.year, d.month, d.day, 0,  0,  0, tzinfo=tz_local).astimezone(timezone.utc)
        fim    = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=tz_local).astimezone(timezone.utc)
        inicio = inicio.replace(tzinfo=None)
        fim    = fim.replace(tzinfo=None)

    elif mes_especifico:
        # Mês completo
        from datetime import datetime, timedelta, timezone
        import calendar
        tz_offset = timedelta(hours=-4)
        tz_local  = timezone(tz_offset)
        y, m = map(int, mes_especifico.split('-'))
        ultimo_dia = calendar.monthrange(y, m)[1]
        inicio = datetime(y, m, 1,          0,  0,  0, tzinfo=tz_local).astimezone(timezone.utc)
        fim    = datetime(y, m, ultimo_dia, 23, 59, 59, tzinfo=tz_local).astimezone(timezone.utc)
        inicio = inicio.replace(tzinfo=None)
        fim    = fim.replace(tzinfo=None)

    else:
        inicio, fim = get_periodo_datas(periodo)

    # ── Query ───────────────────────────────────────────────
    q = Pedido.query.filter(Pedido.data >= inicio, Pedido.data <= fim)
    if origem: q = q.filter(Pedido.origem == origem)
    if forma:  q = q.filter(Pedido.forma_pagamento == forma)
    q = q.order_by(Pedido.data.desc())
    if limit:  q = q.limit(limit)
    pedidos = q.all()

    return jsonify([{
        'id':              p.id,
        'mesa':            p.mesa,
        'produto_nome':    p.produto_nome,
        'produto_preco':   p.produto_preco,
        'quantidade':      p.quantidade,
        'total':           p.total,
        'lucro':           p.lucro,
        'forma_pagamento': p.forma_pagamento,
        'origem':          p.origem,
        'lio_id':          p.lio_id,
        'vendedor_nome':   p.vendedor_nome,
        'setor':           p.setor,
        'data':            hora_local(p.data)
    } for p in pedidos])

@app.route('/api/pedidos/agrupados', methods=['GET'])
@login_required
def pedidos_agrupados():
    origem = request.args.get('origem')
    forma  = request.args.get('forma')
    inicio, fim = get_hoje_utc()
    q = Pedido.query.filter(Pedido.data >= inicio, Pedido.data <= fim)
    if origem: q = q.filter(Pedido.origem == origem)
    if forma:  q = q.filter(Pedido.forma_pagamento == forma)
    pedidos = q.all()
    grupos = {}
    for p in pedidos:
        k = p.produto_nome
        if k not in grupos:
            grupos[k] = {
                'produto_nome':    k,
                'quantidade':      0,
                'total':           0.0,
                'lucro':           0.0,
                'forma_pagamento': p.forma_pagamento,
                'origem':          p.origem,
                'vendedor_nome':   p.vendedor_nome,
                'setor':           p.setor,
            }
        grupos[k]['quantidade'] += p.quantidade
        grupos[k]['total']      += p.total
        grupos[k]['lucro']      += p.lucro
    return jsonify(sorted(grupos.values(), key=lambda x: x['total'], reverse=True))


@app.route('/api/pedidos', methods=['POST'])
@login_required
def criar_pedido():
    data       = request.json
    produto_id = data.get('produto_id')
    produto    = Produto.query.get(produto_id) if produto_id else None
    preco = float(data.get('produto_preco', produto.preco_venda if produto else 0))
    custo = float(data.get('produto_custo', produto.preco_custo if produto else 0))
    qtd   = int(data.get('quantidade', 1))
    total = preco * qtd
    lucro = (preco - custo) * qtd
    p = Pedido(
        mesa=data.get('mesa'),
        produto_nome=data.get('produto_nome', produto.nome if produto else ''),
        produto_preco=preco,
        produto_custo=custo,
        quantidade=qtd,
        total=total,
        lucro=lucro,
        forma_pagamento=data.get('forma_pagamento', 'credito'),
        origem=data.get('origem', 'pdv'),
        lio_id=data.get('lio_id'),
        vendedor_nome=data.get('vendedor_nome'),
        setor=data.get('setor'),
    )
    db.session.add(p)
    if produto:
        produto.estoque = max(0, produto.estoque - qtd)
        if produto.estoque == 0:
            produto.disponivel = False
    db.session.commit()
    return jsonify({'ok': True, 'id': p.id}), 201


# ============================================================
# API DESPESAS
# ============================================================

@app.route('/api/despesas', methods=['GET'])
@login_required
def listar_despesas():
    inicio, fim = get_hoje_utc()
    despesas = Despesa.query.filter(
        Despesa.data >= inicio, Despesa.data <= fim
    ).order_by(Despesa.data.desc()).all()
    return jsonify([{
        'id': d.id, 'descricao': d.descricao, 'valor': d.valor,
        'categoria': d.categoria, 'data': hora_local(d.data)
    } for d in despesas])

@app.route('/api/despesas', methods=['POST'])
@login_required
def criar_despesa():
    data = request.json
    d = Despesa(
        descricao=data['descricao'],
        valor=float(data['valor']),
        categoria=data['categoria']
    )
    db.session.add(d)
    db.session.commit()
    return jsonify({'ok': True, 'id': d.id}), 201

@app.route('/api/despesas/<int:did>', methods=['DELETE'])
@login_required
def excluir_despesa(did):
    d = Despesa.query.get_or_404(did)
    db.session.delete(d)
    db.session.commit()
    return jsonify({'ok': True})

@app.route('/api/despesas/historico', methods=['GET'])
@login_required
def historico_despesas():
    periodo   = request.args.get('periodo')   # 'hoje' | 'semana' | 'mes'
    mes       = request.args.get('mes',  type=int)
    ano       = request.args.get('ano',  type=int)
    categoria = request.args.get('categoria', '')

    agora_utc   = datetime.utcnow()
    agora_local = agora_utc + timedelta(hours=TZ_OFFSET)
    hoje_local  = agora_local.date()

    if periodo == 'hoje':
        inicio_local = hoje_local
        fim_local    = hoje_local
    elif periodo == 'semana':
        inicio_local = hoje_local - timedelta(days=hoje_local.weekday())
        fim_local    = hoje_local
    elif periodo == 'mes':
        inicio_local = hoje_local.replace(day=1)
        fim_local    = hoje_local
    elif mes and ano:
        from calendar import monthrange
        inicio_local = date(ano, mes, 1)
        fim_local    = date(ano, mes, monthrange(ano, mes)[1])
    else:
        inicio_local = hoje_local
        fim_local    = hoje_local

    inicio_dt = datetime.combine(inicio_local, datetime.min.time()) - timedelta(hours=TZ_OFFSET)
    fim_dt    = datetime.combine(fim_local,    datetime.max.time()) - timedelta(hours=TZ_OFFSET)

    q = Despesa.query.filter(Despesa.data >= inicio_dt, Despesa.data <= fim_dt)
    if categoria:
        q = q.filter(Despesa.categoria == categoria)
    despesas = q.order_by(Despesa.data.desc()).all()

    return jsonify([{
        'id':        d.id,
        'descricao': d.descricao,
        'valor':     d.valor,
        'categoria': d.categoria,
        'data':      hora_local(d.data)
    } for d in despesas])

# ============================================================
# API DASHBOARD
# ============================================================

@app.route('/api/dashboard', methods=['GET'])
@login_required
def dashboard():
    periodo = request.args.get('periodo', 'hoje')
    inicio, fim = get_periodo_datas(periodo)
    pedidos  = Pedido.query.filter(Pedido.data >= inicio,  Pedido.data <= fim).all()
    despesas = Despesa.query.filter(Despesa.data >= inicio, Despesa.data <= fim).all()
    faturamento    = sum(p.total for p in pedidos)
    custo_produtos = sum(p.produto_custo * p.quantidade for p in pedidos)
    lucro_bruto    = sum(p.lucro for p in pedidos)
    total_despesas = sum(d.valor for d in despesas)
    lucro_liquido  = lucro_bruto - total_despesas
    por_forma = {}
    for p in pedidos:
        por_forma[p.forma_pagamento] = por_forma.get(p.forma_pagamento, 0) + p.total
    top_raw = {}
    for p in pedidos:
        if p.produto_nome not in top_raw:
            top_raw[p.produto_nome] = {'nome': p.produto_nome, 'qtd': 0, 'total': 0}
        top_raw[p.produto_nome]['qtd']   += p.quantidade
        top_raw[p.produto_nome]['total'] += p.total
    top_produtos = sorted(top_raw.values(), key=lambda x: x['total'], reverse=True)[:5]
    return jsonify({
        'faturamento':         faturamento,
        'custo_produtos':      custo_produtos,
        'lucro_bruto':         lucro_bruto,
        'total_despesas':      total_despesas,
        'lucro_liquido':       lucro_liquido,
        'total_pedidos':       len(pedidos),
        'por_forma_pagamento': por_forma,
        'top_produtos':        top_produtos
    })

@app.route('/api/dashboard/anual', methods=['GET'])
@login_required
def dashboard_anual():
    from sqlalchemy import extract
    ano = request.args.get('ano', datetime.utcnow().year, type=int)
    resultado = []
    for mes in range(1, 13):
        pedidos_mes = Pedido.query.filter(
            extract('year', Pedido.data) == ano,
            extract('month', Pedido.data) == mes
        ).all()
        faturamento_mes = sum(p.total for p in pedidos_mes)
        resultado.append(round(faturamento_mes, 2))
    return jsonify({'ano': ano, 'meses': resultado})
# ============================================================
# FECHAR CAIXA / CIELO / WEBHOOK
# ============================================================

CIELO_LIO_CAIXA = "02186204-0"
CIELO_LIO_API = "https://api-hml-mtls.cielo.com.br/order-management/v1"

def cielo_headers():
    return {
        'Client-Id':    CIELO_CLIENT_ID,
        'Access-Token': CIELO_ACCESS_TOKEN,
        'Content-Type': 'application/json',
        'Accept':       'application/json'
    }

@app.route('/api/fechar-caixa', methods=['POST'])
@login_required
def fechar_caixa():
    inicio, fim = get_hoje_utc()
    Pedido.query.filter(
        Pedido.data >= inicio, Pedido.data <= fim
    ).update({'pago': True})
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/lio/cobrar', methods=['POST'])
@login_required
def lio_cobrar():
    import time as _time

    data          = request.json or {}
    valor         = float(data.get('valor', 0))
    forma         = data.get('forma', 'credito')
    descricao     = data.get('descricao', 'Venda Calcada 190')
    numero_logico = data.get('numero_logico', CIELO_LIO_CAIXA)

    valor_centavos = int(round(valor * 100))

    tipo_map = {
        'credito': 'CREDIT',
        'debito':  'DEBIT',
        'pix':     'PIX',
    }
    payment_type = tipo_map.get(forma, 'CREDIT')

    # 1. Cria o pedido na Cielo
    order_payload = {
        'number':    f'PDV{int(_time.time())}',
        'reference': descricao[:40],
        'items': [{
            'sku':             f'PDV{int(_time.time())}',
            'name':            descricao[:40],
            'unit_price':      valor_centavos,
            'quantity':        1,
            'unit_of_measure': 'EACH'
        }]
    }

    try:
        r1 = requests.post(
            f'{CIELO_LIO_API}/orders',
            json=order_payload,
            headers=cielo_headers(),
            timeout=10
        )
        r1.raise_for_status()
        order_id = r1.json().get('id')
        if not order_id:
            return jsonify({'erro': 'Cielo não retornou order_id'}), 500
    except Exception as e:
        return jsonify({'erro': f'Falha ao criar pedido Cielo: {str(e)}'}), 500

    # 2. Lança a cobrança na LIO pelo número lógico
    tx_payload = {
        'terminal_number': numero_logico,
        'payment_product': payment_type,
        'amount':          valor_centavos,
        'installments':    1
    }

    try:
        r2 = requests.post(
            f'{CIELO_LIO_API}/orders/{order_id}/transactions',
            json=tx_payload,
            headers=cielo_headers(),
            timeout=10
        )
        r2.raise_for_status()
    except Exception as e:
        return jsonify({'erro': f'Falha ao acionar LIO: {str(e)}'}), 500

    return jsonify({
        'ok':       True,
        'order_id': order_id,
        'aviso':    None
    })


@app.route('/api/lio/status/<order_id>', methods=['GET'])
@login_required
def lio_status(order_id):
    try:
        r = requests.get(
            f'{CIELO_LIO_API}/orders/{order_id}',
            headers=cielo_headers(),
            timeout=8
        )
        r.raise_for_status()
        order  = r.json()
        status = order.get('status', '')
        return jsonify({
            'status':    status,
            'aprovado':  status == 'PAID',
            'cancelado': status in ('CANCELED', 'CANCELLED')
        })
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@app.route('/webhook/lio', methods=['POST'])
def webhook_lio():
    data = request.json or {}
    try:
        valor = float(data.get('amount', 0)) / 100
        p = Pedido(
            mesa=data.get('merchantOrderId', ''),
            produto_nome=data.get('description', 'Venda LIO'),
            produto_preco=valor, produto_custo=0, quantidade=1,
            total=valor, lucro=valor,
            forma_pagamento=data.get('paymentType', 'credito').lower(),
            origem='lio',
            lio_id=data.get('terminalId') or data.get('serial_number', '')
        )
        db.session.add(p)
        db.session.commit()
        return jsonify({'ok': True}), 200
    except Exception as e:
        return jsonify({'erro': str(e)}), 400


# ============================================================
# API SYNC — App Android
# ============================================================

@app.route('/app/produtos', methods=['GET'])
@app_auth_required
def app_listar_produtos():
    todos = request.args.get('todos', '0') == '1'
    q = Produto.query.filter_by(ativo=True)
    if not todos:
        q = q.filter_by(disponivel=True)
    prods = q.order_by(Produto.categoria, Produto.nome).all()
    return jsonify([produto_dict(p) for p in prods])

@app.route('/app/produtos/<int:pid>/estoque', methods=['GET'])
@app_auth_required
def app_estoque_produto(pid):
    p = Produto.query.get_or_404(pid)
    return jsonify({
        'id':        p.id,
        'nome':      p.nome,
        'estoque':   p.estoque,
        'disponivel': p.disponivel if p.disponivel is not None else True
    })

@app.route('/app/venda', methods=['POST'])
@app_auth_required
def app_registrar_venda():
    data          = request.json or {}
    lio_id        = data.get('lio_id', '')
    mesa          = data.get('mesa', 'Pista')
    forma         = data.get('forma_pagamento', 'credito')
    itens         = data.get('itens', [])
    vendedor_nome = data.get('vendedor_nome', '')   # ← NOVO
    setor         = data.get('setor', '')            # ← NOVO

    if not itens:
        return jsonify({'erro': 'Nenhum item informado'}), 400

    registrados = []
    erros       = []

    for item in itens:
        pid     = item.get('produto_id')
        qtd     = int(item.get('quantidade', 1))
        produto = Produto.query.get(pid) if pid else None

        if not produto or not produto.ativo:
            erros.append(f'Produto {pid} não encontrado'); continue
        if not produto.disponivel:
            erros.append(f'{produto.nome} está indisponível'); continue
        if produto.estoque < qtd:
            erros.append(f'{produto.nome}: só {produto.estoque} em estoque'); continue

        preco = produto.preco_venda
        custo = produto.preco_custo
        p = Pedido(
            mesa=mesa,
            produto_nome=produto.nome,
            produto_preco=preco,
            produto_custo=custo,
            quantidade=qtd,
            total=preco * qtd,
            lucro=(preco - custo) * qtd,
            forma_pagamento=forma,
            origem='lio',
            lio_id=lio_id,
            vendedor_nome=vendedor_nome,   # ← NOVO
            setor=setor,                   # ← NOVO
        )
        db.session.add(p)
        registrados.append(produto.nome)
        produto.estoque = max(0, produto.estoque - qtd)
        if produto.estoque == 0:
            produto.disponivel = False

    db.session.commit()
    status = 201 if registrados else 400
    return jsonify({
        'ok':          bool(registrados),
        'registrados': registrados,
        'erros':       erros
    }), status

@app.route('/app/sync', methods=['GET'])
@app_auth_required
def app_sync_completo():
    prods = Produto.query.filter_by(ativo=True).order_by(
        Produto.categoria, Produto.nome
    ).all()
    inicio, fim = get_hoje_utc()
    pedidos_hoje = Pedido.query.filter(
        Pedido.data >= inicio, Pedido.data <= fim
    ).all()
    return jsonify({
        'produtos':        [produto_dict(p) for p in prods],
        'total_vendas':    sum(p.total for p in pedidos_hoje),
        'total_pedidos':   len(pedidos_hoje),
        'sincronizado_em': datetime.utcnow().isoformat()
    })

# ============================================================
# RIDERS — Adicionar estas rotas no app.py
# ============================================================
# 1) No topo do app.py, adicione Rider no import:
#    from models import Produto, Pedido, Despesa, Usuario, Rider
#
# 2) Cole todo este bloco antes do:  if __name__ == '__main__':
# ============================================================

@app.route('/riders')
@login_required
def riders_page():
    return render_template('riders.html',
        usuario=session.get('nome'), perfil=session.get('perfil'),
        active_page='riders')

# --- Listar todos os riders ---
@app.route('/api/riders', methods=['GET'])
@login_required
def listar_riders():
    riders = Rider.query.order_by(Rider.criado_em.desc()).all()
    return jsonify([r.to_dict() for r in riders])

# --- Criar novo rider ---
@app.route('/api/riders', methods=['POST'])
@login_required
def criar_rider():
    data = request.json or {}
    nome  = data.get('nome', '').upper().strip()
    dt    = data.get('data', '')
    cache = float(data.get('cache', 0))
    if not nome or not dt:
        return jsonify({'erro': 'Nome e data são obrigatórios'}), 400
    r = Rider(nome=nome, data=dt, cache=cache, encerrado=False)
    r.itens_rider  = data.get('itens_rider', [])
    r.consumo_extra = []
    db.session.add(r)
    db.session.commit()
    return jsonify({'ok': True, 'id': r.id}), 201

# --- Entregar item do rider (baixa no estoque) ---
@app.route('/api/riders/<int:rid>/entregar/<int:idx>', methods=['POST'])
@login_required
def entregar_item_rider(rid, idx):
    r = Rider.query.get_or_404(rid)
    if r.encerrado:
        return jsonify({'erro': 'Rider já encerrado'}), 400
    itens = r.itens_rider
    if idx >= len(itens):
        return jsonify({'erro': 'Item não encontrado'}), 404
    item = itens[idx]
    if item.get('entregues', 0) >= item.get('quantidade', 0):
        return jsonify({'erro': 'Todos os itens já foram entregues'}), 400
    # Dá baixa no estoque do produto
    prod = Produto.query.get(item.get('produto_id'))
    qtd_por_entrega = 1  # cada clique = 1 unidade
    if prod:
        if prod.estoque < qtd_por_entrega:
            return jsonify({'erro': f'Estoque insuficiente: {prod.nome} tem só {prod.estoque}'}), 400
        prod.estoque = max(0, prod.estoque - qtd_por_entrega)
        if prod.estoque == 0:
            prod.disponivel = False
    itens[idx]['entregues'] = item.get('entregues', 0) + qtd_por_entrega
    r.itens_rider = itens
    db.session.commit()
    return jsonify({'ok': True, 'rider': r.to_dict()})

# --- Adicionar consumo extra ---
@app.route('/api/riders/<int:rid>/consumo', methods=['POST'])
@login_required
def adicionar_consumo_rider(rid):
    r = Rider.query.get_or_404(rid)
    if r.encerrado:
        return jsonify({'erro': 'Rider já encerrado'}), 400
    data = request.json or {}
    pessoa      = data.get('pessoa', '').upper().strip()
    produto_id  = data.get('produto_id')
    produto_nom = data.get('produto_nome', '')
    qtd         = int(data.get('quantidade', 1))
    valor       = float(data.get('valor', 0))
    if not pessoa or not produto_nom:
        return jsonify({'erro': 'Pessoa e produto são obrigatórios'}), 400
    # Dá baixa no estoque
    prod = Produto.query.get(produto_id) if produto_id else None
    if prod:
        if prod.estoque < qtd:
            return jsonify({'erro': f'Estoque insuficiente: {prod.nome} tem só {prod.estoque}'}), 400
        prod.estoque = max(0, prod.estoque - qtd)
        if prod.estoque == 0:
            prod.disponivel = False
    consumos = r.consumo_extra
    consumos.append({
        'pessoa':       pessoa,
        'produto_id':   produto_id,
        'produto_nome': produto_nom,
        'quantidade':   qtd,
        'valor':        valor,
        'hora':         datetime.utcnow().strftime('%H:%M')
    })
    r.consumo_extra = consumos
    db.session.commit()
    return jsonify({'ok': True, 'rider': r.to_dict()})

# --- Remover consumo extra ---
@app.route('/api/riders/<int:rid>/consumo/<int:idx>', methods=['DELETE'])
@login_required
def remover_consumo_rider(rid, idx):
    r = Rider.query.get_or_404(rid)
    if r.encerrado:
        return jsonify({'erro': 'Rider já encerrado'}), 400
    consumos = r.consumo_extra
    if idx >= len(consumos):
        return jsonify({'erro': 'Consumo não encontrado'}), 404
    consumos.pop(idx)
    r.consumo_extra = consumos
    db.session.commit()
    return jsonify({'ok': True})

# --- Encerrar rider ---
# --- Encerrar rider ---
@app.route('/api/riders/<int:rid>/encerrar', methods=['POST'])
@login_required
def encerrar_rider(rid):
    r = Rider.query.get_or_404(rid)
    if r.encerrado:
        return jsonify({'erro': 'Rider já encerrado'}), 400
    r.encerrado = True

    # Cria despesa automaticamente na categoria Banda
    d = Despesa(
        descricao=f"Cachê — {r.nome} ({r.data})",
        valor=r.cache,
        categoria='Banda'
    )
    db.session.add(d)
    db.session.commit()
    return jsonify({'ok': True})

# --- Relatório PDF do rider ---
@app.route('/api/riders/<int:rid>/relatorio', methods=['GET'])
@login_required
def relatorio_rider(rid):
    r = Rider.query.get_or_404(rid)
    consumo_total = sum(c['valor'] for c in r.consumo_extra)
    saldo = r.cache - consumo_total

    linhas_rider = ''.join([
        f"<tr><td>{i['produto_nome']}</td><td>{i['quantidade']}</td>"
        f"<td>{i.get('entregues',0)}</td><td>Da casa</td></tr>"
        for i in r.itens_rider
    ])
    linhas_consumo = ''.join([
        f"<tr><td>{c['pessoa']}</td><td>{c['produto_nome']}</td>"
        f"<td>{c['quantidade']}</td><td style='color:#c0392b'>− R$ {c['valor']:.2f}</td>"
        f"<td>{c.get('hora','')}</td></tr>"
        for c in r.consumo_extra
    ]) or '<tr><td colspan="5" style="text-align:center;color:#999">Nenhum consumo extra</td></tr>'

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
    <title>Rider — {r.nome}</title>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 30px; color: #222; }}
        h1 {{ color: #FF5500; font-size: 28px; margin-bottom: 4px; }}
        .info {{ color: #666; font-size: 13px; margin-bottom: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
        th {{ background: #f5f5f5; padding: 8px 12px; text-align: left; font-size: 12px; text-transform: uppercase; border-bottom: 2px solid #ddd; }}
        td {{ padding: 8px 12px; border-bottom: 1px solid #eee; font-size: 13px; }}
        .saldo-box {{ background: #f9f9f9; border: 2px solid #FF5500; border-radius: 8px; padding: 16px 20px; display: inline-block; margin-bottom: 20px; }}
        .saldo-box .label {{ font-size: 11px; text-transform: uppercase; color: #999; }}
        .saldo-box .valor {{ font-size: 32px; font-weight: bold; color: {'#00a550' if saldo >= 0 else '#c0392b'}; }}
        h2 {{ font-size: 16px; margin: 20px 0 8px; color: #333; border-bottom: 1px solid #eee; padding-bottom: 6px; }}
        @media print {{ body {{ padding: 10px; }} }}
    </style></head><body>
    <h1>🎸 {r.nome}</h1>
    <div class="info">📅 {r.data} &nbsp;·&nbsp; Cachê: R$ {r.cache:.2f} &nbsp;·&nbsp;
    Status: {'Encerrado' if r.encerrado else 'Ativo'}</div>

    <div class="saldo-box">
        <div class="label">Saldo do Cachê</div>
        <div class="valor">R$ {saldo:.2f}</div>
        <div style="font-size:12px;color:#999">Consumido: R$ {consumo_total:.2f}</div>
    </div>

    <h2>🍺 Rider Permitido (da casa)</h2>
    <table><thead><tr><th>Produto</th><th>Qtd Permitida</th><th>Entregues</th><th>Valor</th></tr></thead>
    <tbody>{linhas_rider or '<tr><td colspan="4" style="text-align:center;color:#999">Nenhum item</td></tr>'}</tbody></table>

    <h2>💸 Consumo Extra</h2>
    <table><thead><tr><th>Pessoa</th><th>Produto</th><th>Qtd</th><th>Valor</th><th>Hora</th></tr></thead>
    <tbody>{linhas_consumo}</tbody></table>

    <div style="margin-top:30px;font-size:11px;color:#aaa;border-top:1px solid #eee;padding-top:12px">
        Gerado em {datetime.utcnow().strftime('%d/%m/%Y às %H:%M')} — Calçada 190ML
    </div>
    <script>window.print();</script>
    </body></html>"""

    from flask import Response
    return Response(html, mimetype='text/html')

@app.route('/agenda')
@login_required
def agenda_page():
    return render_template(
        'agenda.html',
        usuario=session.get('nome'),
        perfil=session.get('perfil'),
        active_page='agenda'
    )

@app.route('/api/agenda', methods=['GET'])
@login_required
def listar_eventos():
    eventos = Evento.query.order_by(Evento.data, Evento.hora).all()
    return jsonify([e.to_dict() for e in eventos])
 
@app.route('/api/agenda', methods=['POST'])
@login_required
def criar_evento():
    data = request.json or {}
    nome  = data.get('nome', '').upper().strip()
    dt    = data.get('data', '')
    hora  = data.get('hora', '')
    cache = float(data.get('cache', 0))
    obs   = data.get('obs', '')
    if not nome or not dt or not hora:
        return jsonify({'erro': 'Nome, data e hora são obrigatórios'}), 400
    ev = Evento(nome=nome, data=dt, hora=hora, cache=cache, obs=obs)
    db.session.add(ev)
    db.session.commit()
    return jsonify({'ok': True, 'id': ev.id}), 201
 
@app.route('/api/agenda/<int:eid>', methods=['PUT'])
@login_required
def editar_evento(eid):
    ev = Evento.query.get_or_404(eid)
    data = request.json or {}
    ev.nome  = data.get('nome', ev.nome).upper().strip()
    ev.data  = data.get('data', ev.data)
    ev.hora  = data.get('hora', ev.hora)
    ev.cache = float(data.get('cache', ev.cache))
    ev.obs   = data.get('obs', ev.obs)
    db.session.commit()
    return jsonify({'ok': True})
 
@app.route('/api/agenda/<int:eid>', methods=['DELETE'])
@login_required
def excluir_evento(eid):
    ev = Evento.query.get_or_404(eid)
    db.session.delete(ev)
    db.session.commit()
    return jsonify({'ok': True})


# ============================================================
# API VENDEDORES ATIVOS — Check-in do app Android
# ============================================================

# Dicionário em memória: { "nome_vendedor": { dados } }
# Simples e eficiente — reseta quando o servidor reinicia (ok, é por dia)
vendedores_ativos = {}

@app.route('/app/checkin', methods=['POST'])
@app_auth_required
def app_checkin():
    data          = request.json or {}
    nome          = data.get('vendedor_nome', '').strip()
    setor         = data.get('setor', '').strip()
    lio_id        = data.get('lio_id', '')
    if not nome:
        return jsonify({'erro': 'Nome obrigatório'}), 400

    vendedores_ativos[nome] = {
        'vendedor_nome': nome,
        'setor':         setor,
        'lio_id':        lio_id,
        'ultimo_ping':   datetime.utcnow().isoformat(),
        'online':        True
    }
    return jsonify({'ok': True})

@app.route('/app/heartbeat', methods=['POST'])
@app_auth_required
def app_heartbeat():
    data = request.json or {}
    nome = data.get('vendedor_nome', '').strip()
    if nome and nome in vendedores_ativos:
        vendedores_ativos[nome]['ultimo_ping'] = datetime.utcnow().isoformat()
        vendedores_ativos[nome]['online']      = True
    return jsonify({'ok': True})

@app.route('/app/checkout', methods=['POST'])
@app_auth_required
def app_checkout():
    data = request.json or {}
    nome = data.get('vendedor_nome', '').strip()
    if nome in vendedores_ativos:
        del vendedores_ativos[nome]
    return jsonify({'ok': True})

@app.route('/api/vendedores-ativos', methods=['GET'])
@login_required
def listar_vendedores_ativos():
    # Marca como offline quem não mandou heartbeat há mais de 3 minutos
    agora = datetime.utcnow()
    for nome, v in vendedores_ativos.items():
        try:
            ultimo = datetime.fromisoformat(v['ultimo_ping'])
            v['online'] = (agora - ultimo).total_seconds() < 180
        except:
            v['online'] = False
    return jsonify(list(vendedores_ativos.values()))

@app.route('/app/vendas', methods=['GET'])
@app_auth_required
def app_listar_vendas():
    limit  = request.args.get('limit', 20, type=int)
    periodo = request.args.get('periodo', 'hoje')  # hoje | semana | mes | tudo

    if periodo == 'tudo':
        pedidos = Pedido.query.order_by(Pedido.data.desc()).limit(limit).all()
    else:
        inicio, fim = get_periodo_datas(periodo)
        pedidos = Pedido.query.filter(
            Pedido.data >= inicio, Pedido.data <= fim
        ).order_by(Pedido.data.desc()).limit(limit).all()

    return jsonify([{
        'id':              p.id,
        'mesa':            p.mesa or 'Pista',
        'produto_nome':    p.produto_nome,
        'produto_preco':   p.produto_preco,
        'quantidade':      p.quantidade,
        'total':           p.total,
        'forma_pagamento': p.forma_pagamento,
        'vendedor_nome':   p.vendedor_nome or '',
        'setor':           p.setor or '',
        'data':            hora_local(p.data),
    } for p in pedidos])

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)