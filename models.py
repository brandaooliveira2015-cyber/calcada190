from database import db
from datetime import datetime
import json


class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    preco_venda = db.Column(db.Float, nullable=False)
    preco_custo = db.Column(db.Float, nullable=False, default=0)
    categoria = db.Column(db.String(50), nullable=False)
    estoque = db.Column(db.Integer, default=0)
    estoque_minimo = db.Column(db.Integer, default=0)
    foto = db.Column(db.String(200), nullable=True)
    ativo = db.Column(db.Boolean, default=True)
    disponivel = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)


class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mesa = db.Column(db.String(50), nullable=True)
    produto_nome = db.Column(db.String(100), nullable=False)
    produto_preco = db.Column(db.Float, nullable=False)
    produto_custo = db.Column(db.Float, nullable=False, default=0)
    quantidade = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Float, nullable=False)
    lucro = db.Column(db.Float, nullable=False, default=0)
    forma_pagamento = db.Column(db.String(20), default='credito')
    origem = db.Column(db.String(20), default='pdv')
    lio_id = db.Column(db.String(50), nullable=True)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    pago = db.Column(db.Boolean, default=False)
    vendedor_nome = db.Column(db.String(100), nullable=True)
    setor = db.Column(db.String(50), nullable=True)


class Despesa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(100), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    data = db.Column(db.DateTime, default=datetime.utcnow)


class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    login = db.Column(db.String(50), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    perfil = db.Column(db.String(20), default='operador')
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    token_reset = db.Column(db.String(100), nullable=True)
    token_expira = db.Column(db.DateTime, nullable=True)


class Rider(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    data = db.Column(db.String(20), nullable=False)
    cache = db.Column(db.Float, nullable=False, default=0)
    itens_rider_json = db.Column(db.Text, default='[]')
    consumo_extra_json = db.Column(db.Text, default='[]')
    encerrado = db.Column(db.Boolean, default=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def itens_rider(self):
        try:
            return json.loads(self.itens_rider_json or '[]')
        except:
            return []

    @itens_rider.setter
    def itens_rider(self, value):
        self.itens_rider_json = json.dumps(value, ensure_ascii=False)

    @property
    def consumo_extra(self):
        try:
            return json.loads(self.consumo_extra_json or '[]')
        except:
            return []

    @consumo_extra.setter
    def consumo_extra(self, value):
        self.consumo_extra_json = json.dumps(value, ensure_ascii=False)

    def to_dict(self):
        return {
            'id':            self.id,
            'nome':          self.nome,
            'data':          self.data,
            'cache':         self.cache,
            'itens_rider':   self.itens_rider,
            'consumo_extra': self.consumo_extra,
            'encerrado':     self.encerrado,
            'criado_em':     self.criado_em.strftime('%d/%m/%Y %H:%M') if self.criado_em else ''
        }


class Evento(db.Model):
    __tablename__ = 'eventos'
    id        = db.Column(db.Integer, primary_key=True)
    nome      = db.Column(db.String(200), nullable=False)
    data      = db.Column(db.String(10),  nullable=False)   # YYYY-MM-DD
    hora      = db.Column(db.String(5),   nullable=False)   # HH:MM
    cache     = db.Column(db.Float, default=0.0)
    obs       = db.Column(db.Text, default='')
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':    self.id,
            'nome':  self.nome,
            'data':  self.data,
            'hora':  self.hora,
            'cache': self.cache,
            'obs':   self.obs,
        }