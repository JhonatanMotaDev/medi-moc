import pandas as pd

from src.normalize import normalize
from src.parse import parse_response


def test_parse_and_normalize_preserves_identifiers_and_brazilian_numbers():
    html = '''
    <table>
      <thead><tr><th>Código unidade</th><th>Unidade</th><th>Medicamento</th><th>Estoque</th></tr></thead>
      <tbody><tr><td>007</td><td> UBS Centro </td><td>Dipirona 500 mg</td><td>1.250</td></tr></tbody>
    </table>
    '''
    raw = parse_response(html, "text/html")
    df = normalize(raw)

    assert df.loc[0, "codigo_municipio"] == "3143302"
    assert df.loc[0, "codigo_unidade"] == "007"
    assert df.loc[0, "unidade"] == "UBS Centro"
    assert df.loc[0, "medicamento"] == "Dipirona 500 mg"
    assert df.loc[0, "quantidade_estoque"] == 1250


def test_duplicates_are_removed():
    df = pd.DataFrame({
        "Código unidade": ["1", "1"],
        "Unidade": ["A", "A"],
        "Medicamento": ["X", "X"],
        "Estoque": ["10", "10"],
    })
    assert len(normalize(df)) == 1
