"""Gera somente dados sintéticos, reproduzíveis e sem informações pessoais reais."""
import csv
import json
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path

BASE_DATE = date(2026, 10, 13)
WAREHOUSES = [(1, 'CD Cuiabá', 'Cuiabá / MT'), (2, 'CD Campo Grande', 'Campo Grande / MS'),
              (3, 'CD Rondonópolis', 'Rondonópolis / MT')]
CATALOG = {
    'Eletrônicos': ['Cabo USB-C', 'Carregador 20W', 'Fone sem fio', 'Mouse óptico', 'Teclado compacto', 'Hub USB', 'Suporte notebook', 'Caixa de som', 'Webcam HD', 'Power bank', 'Adaptador HDMI', 'Luminária LED'],
    'Casa e cozinha': ['Jogo de copos', 'Garrafa térmica', 'Panela inox', 'Pote hermético', 'Jogo de talheres', 'Escorredor', 'Tábua de corte', 'Caneca cerâmica', 'Assadeira', 'Organizador', 'Jarra de vidro', 'Balança cozinha'],
    'Papelaria': ['Caderno A5', 'Caneta azul', 'Marcador texto', 'Pasta catálogo', 'Bloco adesivo', 'Envelope kraft', 'Estojo escolar', 'Lápis HB', 'Régua 30 cm', 'Grampeador', 'Agenda semanal', 'Papel A4'],
    'Limpeza': ['Detergente 500 ml', 'Desinfetante 1 L', 'Sabão líquido', 'Esponja multiuso', 'Pano microfibra', 'Álcool 70%', 'Luva borracha', 'Saco lixo 50 L', 'Vassoura', 'Rodo 40 cm', 'Balde 10 L', 'Limpador vidro'],
    'Ferramentas': ['Chave Philips', 'Trena 5 m', 'Alicate universal', 'Martelo', 'Kit parafusos', 'Fita isolante', 'Broca aço', 'Nível bolha', 'Chave inglesa', 'Lanterna', 'Óculos proteção', 'Fita veda rosca'],
    'Esporte e lazer': ['Squeeze 750 ml', 'Corda de pular', 'Faixa elástica', 'Tapete yoga', 'Bola futebol', 'Bomba de ar', 'Luva ciclismo', 'Toalha esportiva', 'Mochila leve', 'Boné esportivo', 'Munhequeira', 'Bolsa academia'],
}


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def generate(folder=None):
    folder = Path(folder or Path(__file__).parent / 'data')
    folder.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20261013)
    warehouses = [dict(id=i, nome=name, cidade=city) for i, name, city in WAREHOUSES]
    products, stocks, movements = [], [], []
    for category, names in CATALOG.items():
        for name in names:
            sku = f'AT-{len(products)+1:04d}'
            products.append(dict(sku=sku, nome=name, categoria=category,
                                 custo_unitario_centavos=rng.randint(600, 49900)))
            for warehouse_id, _, _ in WAREHOUSES:
                opening = rng.randint(35, 180)
                minimum = rng.randint(18, 45)
                stocks.append(dict(id=len(stocks)+1, sku=sku, cd_id=warehouse_id,
                                   saldo_inicial=opening, quantidade=opening,
                                   estoque_minimo=minimum, estoque_maximo=minimum*8))
    for day in range(30):
        for hour in range(20):
            stock = rng.choice(stocks)
            incoming = rng.random() < .42 or stock['quantidade'] == 0
            quantity = rng.randint(5, 40) if incoming else -rng.randint(1, min(35, stock['quantidade']))
            stamp = datetime.combine(BASE_DATE - timedelta(days=29-day), time(8 + hour // 2, (hour % 2)*30))
            stock['quantidade'] += quantity
            movements.append(dict(id=len(movements)+1, estoque_id=stock['id'],
                                  tipo='entrada' if incoming else 'saida', quantidade=quantity,
                                  data_hora=stamp.isoformat(timespec='minutes'),
                                  documento=f'SIM-{len(movements)+1:05d}'))
    # Explicit stockout/low-stock scenarios, also recorded in the stock ledger.
    for index, stock in enumerate(stocks[:26]):
        target = 0 if index < 8 else max(1, stock['estoque_minimo']//2)
        delta = target - stock['quantidade']
        stock['quantidade'] = target
        movements.append(dict(id=len(movements)+1, estoque_id=stock['id'], tipo='ajuste',
                              quantidade=delta, data_hora=f'{BASE_DATE.isoformat()}T18:{index:02d}',
                              documento=f'SIM-AJUSTE-{index+1:03d}'))
    for name, rows in [('centros_ficticios.csv', warehouses), ('produtos_ficticios.csv', products),
                       ('estoque_ficticio.csv', stocks), ('movimentacoes_ficticias.csv', movements)]:
        write_csv(folder/name, rows)
    metadata = dict(synthetic=True, data_referencia=BASE_DATE.isoformat(), seed=20261013,
                    produtos=len(products), centros=len(warehouses), posicoes=len(stocks),
                    movimentacoes=len(movements), moeda='BRL',
                    regra_saldo='quantidade = saldo_inicial + soma das movimentações assinadas',
                    regra_critico='quantidade <= estoque_minimo; ruptura = quantidade igual a zero')
    (folder/'metadados.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    return metadata


if __name__ == '__main__':
    print(json.dumps(generate(), ensure_ascii=True))
